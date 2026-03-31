# Dynantic — Advanced Patterns

## Table of Contents
1. [Polymorphism (Single-Table Design)](#polymorphism-single-table-design)
2. [FastAPI Integration](#fastapi-integration)
3. [Testing with LocalStack](#testing-with-localstack)
4. [Testing with Mocks](#testing-with-mocks)

---

## Polymorphism (Single-Table Design)

Store multiple entity types in one DynamoDB table. The `Discriminator()` field auto-populates and routes deserialization to the correct subclass.

### Define the Base Entity

```python
from dynantic import DynamoModel, Key, SortKey, Discriminator

class Entity(DynamoModel):
    pk: str = Key()
    sk: str = SortKey()
    entity_type: str = Discriminator()

    class Meta:
        table_name = "AppTable"
```

### Register Subclasses

```python
@Entity.register("USER")
class UserEntity(Entity):
    email: str
    name: str

@Entity.register("ORDER")
class OrderEntity(Entity):
    order_id: str
    total: Decimal
    status: str = "pending"

@Entity.register("PRODUCT")
class ProductEntity(Entity):
    product_name: str
    price: Decimal
    category: str
```

### How It Works

1. `Discriminator()` marks the field used to differentiate entity types
2. `@Entity.register("USER")` binds the string `"USER"` to `UserEntity`
3. On `save()`, the discriminator value is auto-injected (you don't set it manually)
4. On `query()`/`scan()` from the **base** class, items are deserialized to the correct subclass based on discriminator
5. On `query()`/`scan()` from a **subclass**, results are auto-filtered to that entity type only

### Usage

```python
# Save different entity types to the same table
user = UserEntity(pk="USER#alice", sk="PROFILE", email="alice@example.com", name="Alice")
user.save()

order = OrderEntity(pk="USER#alice", sk="ORDER#001", order_id="001", total=Decimal("99.99"))
order.save()

# Query from base → returns mixed types, correctly deserialized
items = Entity.query("USER#alice").all()
for item in items:
    if isinstance(item, UserEntity):
        print(f"User: {item.name}")
    elif isinstance(item, OrderEntity):
        print(f"Order: {item.order_id} — ${item.total}")

# Query from subclass → auto-filtered to that type only
orders = OrderEntity.query("USER#alice").all()  # Only OrderEntity instances
```

### Key Design Pattern

Use structured key prefixes for clean access patterns:

| Entity | PK | SK |
|--------|----|----|
| User profile | `USER#<user_id>` | `PROFILE` |
| User order | `USER#<user_id>` | `ORDER#<order_id>` |
| Product | `PRODUCT#<product_id>` | `METADATA` |

---

## FastAPI Integration

Dynantic is synchronous. For FastAPI, either use sync endpoints or wrap calls with `asyncio.to_thread()`.

### Sync Endpoints (Simplest)

```python
from fastapi import APIRouter, HTTPException, Query

from dynantic import Attr

from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse)
def create_user(body: UserCreate):
    user = User(**body.model_dump())
    try:
        user.save(condition=Attr("email").not_exists())
    except ConditionalCheckFailedError:
        raise HTTPException(409, "User already exists")
    return user

@router.get("/{email}", response_model=UserResponse)
def get_user(email: str):
    user = User.get(email)
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

### Async Endpoints

```python
import asyncio

@router.get("/{email}", response_model=UserResponse)
async def get_user(email: str):
    user = await asyncio.to_thread(User.get, email)
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

### Paginated List Endpoint

```python
from typing import Any

from pydantic import BaseModel

class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: dict[str, Any] | None
    has_more: bool

@router.get("/{user_id}/orders", response_model=PaginatedResponse)
def list_orders(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
):
    start_key = json.loads(cursor) if cursor else None
    page = Order.query(user_id).limit(limit).page(start_key=start_key)
    return PaginatedResponse(
        items=[o.model_dump() for o in page.items],
        next_cursor=page.last_evaluated_key,
        has_more=page.has_more,
    )
```

### Service Layer Pattern

Keep DynamoDB logic in services, not routers:

```python
# app/services/user_service.py
from dynantic import Attr
from dynantic.exceptions import ConditionalCheckFailedError

from app.models.user import User
from app.schemas.user import UserCreate

class UserService:
    @staticmethod
    def create(data: UserCreate) -> User:
        user = User(**data.model_dump())
        user.save(condition=Attr("email").not_exists())
        return user

    @staticmethod
    def get_by_email(email: str) -> User | None:
        return User.get(email)

    @staticmethod
    def increment_login(email: str) -> None:
        User.update(email).add(User.login_count, 1).execute()
```

```python
# app/routers/users.py
from app.services.user_service import UserService

@router.post("/", response_model=UserResponse)
def create_user(body: UserCreate):
    try:
        return UserService.create(body)
    except ConditionalCheckFailedError:
        raise HTTPException(409, "User already exists")
```

---

## Testing with LocalStack

Use LocalStack to run integration tests against a real DynamoDB emulation.

### docker-compose.yaml

```yaml
services:
  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=dynamodb
```

### Pytest Fixture

```python
import boto3
import pytest

from dynantic import DynamoModel

@pytest.fixture(scope="session")
def dynamo_client():
    client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:4566",
        region_name="eu-west-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    DynamoModel.set_client(client)
    return client

@pytest.fixture(autouse=True)
def create_tables(dynamo_client):
    # Create table before each test
    try:
        dynamo_client.create_table(
            TableName="users",
            KeySchema=[
                {"AttributeName": "email", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
    except dynamo_client.exceptions.ResourceInUseException:
        pass
    yield
    # Clean up after test
    dynamo_client.delete_table(TableName="users")
```

### Integration Test

```python
def test_save_and_get(dynamo_client):
    user = User(email="test@example.com", name="Test", age=25)
    user.save()

    retrieved = User.get("test@example.com")
    assert retrieved is not None
    assert retrieved.name == "Test"
    assert retrieved.age == 25
```

---

## Testing with Mocks

For fast unit tests without DynamoDB:

```python
from unittest.mock import MagicMock

import pytest

from dynantic import DynamoModel

@pytest.fixture(autouse=True)
def mock_dynamo():
    mock_client = MagicMock()
    DynamoModel.set_client(mock_client)
    yield mock_client
    DynamoModel.set_client(None)

def test_get_user(mock_dynamo):
    mock_dynamo.get_item.return_value = {
        "Item": {
            "email": {"S": "alice@example.com"},
            "name": {"S": "Alice"},
            "age": {"N": "30"},
        }
    }

    user = User.get("alice@example.com")
    assert user is not None
    assert user.name == "Alice"
    assert user.age == 30

    mock_dynamo.get_item.assert_called_once()
```
