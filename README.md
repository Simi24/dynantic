<p align="center">
    <img src="assets/dyno_dynantic.png" alt="Dynantic" width="600" />
</p>

# Dynantic

**Type-safe DynamoDB ORM with Pydantic validation** 

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

> ⚠️ **Beta Software**: Dynantic is in active development. The API is stable, but you may encounter rough edges. Production use is at your own risk. Feedback and contributions are welcome!

---

## What is Dynantic?

Dynantic is a **synchronous-first** Python ORM for Amazon DynamoDB that combines:
- ✅ **Pydantic v2** validation and type safety
- ✅ **Metaclass-based DSL** for elegant query building
- ✅ **Comprehensive type support** (datetime, UUID, Enum, Decimal, sets, etc.)
- ✅ **Global Secondary Indexes** (GSI)
- ✅ **Polymorphic models** for single-table design
- ✅ **Conditional writes** with SQLModel-like syntax
- ✅ **Atomic updates** without fetching first
- ✅ **External pagination** for stateless APIs
- ✅ **Batch operations** with auto-chunking and retry
- ✅ **ACID transactions** across tables
- ✅ **TTL support** with automatic datetime/epoch conversion
- ✅ **Auto-UUID** with `Key(auto=True)` and INSERT-safe `create()`

**Optimized for**: AWS Lambda, serverless functions, FastAPI (with threadpool), batch jobs, and scripts.

---


## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Why Dynantic?](#why-dynantic)
- [Core Concepts](#core-concepts)
  - [Model Definition](#model-definition)
  - [CRUD Operations](#crud-operations)
  - [Querying](#querying)
  - [Atomic Updates](#atomic-updates)
  - [Conditional Writes](#conditional-writes)
  - [Batch Operations](#batch-operations)
  - [Transactions](#transactions)
  - [TTL (Time To Live)](#ttl-time-to-live)
  - [Auto-UUID](#auto-uuid)
  - [Pagination](#pagination)
  - [Polymorphism](#polymorphism)
- [Configuration](#configuration)
  - [AWS Setup](#aws-setup)
  - [Boto3 Client Configuration](#boto3-client-configuration)
  - [Testing with LocalStack](#testing-with-localstack)
- [Async Usage](#async-usage)
- [Limitations](#limitations)
- [Security Considerations](#security-considerations)
- [Performance Tips](#performance-tips)
- [Comparison with Alternatives](#comparison-with-alternatives)
- [Contributing](#contributing)
- [License](#license)

---

## Installation

```bash
pip install dynantic
```

**Requirements:**
- Python 3.10+
- boto3 >= 1.34.0
- pydantic >= 2.6.0

---

## Quick Start

```python
from datetime import datetime, timezone
from enum import Enum
from dynantic import DynamoModel, Key, SortKey

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class User(DynamoModel):
    user_id: str = Key()
    email: str = SortKey()
    name: str
    status: UserStatus
    created_at: datetime
    balance: float
    tags: set[str]

    class Meta:
        table_name = "users"

# Create
user = User(
    user_id="user-123",
    email="john@example.com",
    name="John Doe",
    status=UserStatus.ACTIVE,
    created_at=datetime.now(timezone.utc),
    balance=99.99,
    tags={"premium", "verified"}
)
user.save()

# Read
user = User.get("user-123", "john@example.com")
print(f"User: {user.name}, Status: {user.status.value}")

# Update (atomic)
User.update("user-123", "john@example.com") \
    .add(User.balance, 10.0) \
    .add(User.tags, {"early_adopter"}) \
    .execute()

# Delete
User.delete("user-123", "john@example.com")
```

---

## Why Dynantic?

### ✅ What Dynantic Does Well

1. **Type Safety**: Full Pydantic validation with IDE autocomplete
2. **Developer Experience**: Elegant DSL for queries and conditions
3. **Lambda-Optimized**: Sync-first design keeps cold starts fast
4. **Battle-Tested Patterns**: Implements DynamoDB best practices
5. **Zero Magic**: Transparent serialization, no hidden state

### ❌ What Dynantic Doesn't Do

1. **Async Support**: Synchronous only (use threadpool for FastAPI)
2. **Schema Migrations**: You manage table creation yourself
3. **Relationships**: No automatic joins (DynamoDB doesn't support them anyway)

---

## Core Concepts

### Model Definition

#### Basic Model (Partition Key Only)

```python
from dynantic import DynamoModel, Key

class Product(DynamoModel):
    product_id: str = Key()
    name: str
    price: float
    in_stock: bool

    class Meta:
        table_name = "products"
```

#### With Sort Key

```python
from dynantic import DynamoModel, Key, SortKey

class Order(DynamoModel):
    customer_id: str = Key()
    order_id: str = SortKey()
    total: float
    items: list[str]

    class Meta:
        table_name = "orders"
```

#### With Global Secondary Index

```python
from dynantic import DynamoModel, Key, SortKey, GSIKey, GSISortKey

class BlogPost(DynamoModel):
    post_id: str = Key()
    author_id: str = SortKey()
    title: str
    content: str
    published_at: datetime
    
    # GSI for querying by category + slug
    category: str = GSIKey(index_name="CategoryIndex")
    slug: str = GSISortKey(index_name="CategoryIndex")

    class Meta:
        table_name = "blog_posts"
```

---

### CRUD Operations

#### Create/Save

```python
product = Product(
    product_id="prod-123",
    name="Widget",
    price=29.99,
    in_stock=True
)
product.save()

# With condition (create-if-not-exists)
product.save(condition=Product.product_id.not_exists())
```

#### Read/Get

```python
# By partition key only
product = Product.get("prod-123")

# By partition + sort key
order = Order.get("customer-456", "order-789")

# Returns None if not found (no exception)
missing = Product.get("nonexistent")  # None
```

#### Update

```python
# Fetch then save
product = Product.get("prod-123")
product.price = 34.99
product.save()
```

#### Delete

```python
# By key (no fetch required)
Product.delete("prod-123")

# Or from instance
product = Product.get("prod-123")
product.delete_item()

# With condition
Product.delete("prod-123", condition=Product.in_stock == False)
```

---

### Querying

#### Basic Query

```python
# Query by partition key
orders = Order.query("customer-456").all()

# First result only
first_order = Order.query("customer-456").first()

# Limit results
recent_orders = Order.query("customer-456").limit(10).all()
```

#### Sort Key Conditions

```python
# Exact match
order = Order.query("customer-456").eq("order-789").first()

# Prefix match
posts_2023 = BlogPost.query("author-123").starts_with("2023-").all()

# Range queries
posts = BlogPost.query("author-123").between(
    datetime(2023, 1, 1, tzinfo=timezone.utc),
    datetime(2023, 12, 31, tzinfo=timezone.utc)
).all()

# Comparisons
expensive = Product.query("category").gt(100.0).all()
cheap = Product.query("category").lt(10.0).all()
```

#### GSI Queries

```python
# Query by GSI partition key
tech_posts = BlogPost.query_index("CategoryIndex", "technology").all()

# With sort key condition
recent_tech = BlogPost.query_index("CategoryIndex", "technology") \
    .starts_with("2024-") \
    .limit(20) \
    .all()
```

#### Filtering (Non-Key Attributes)

**Filter results on non-key attributes** during queries or scans:

```python
from dynantic import Attr

# Query with filter on non-key field
high_rated = Movie.query(2013).filter(Movie.rating >= 8.0).all()

# Multiple filters (combined with AND)
popular_dramas = (Movie.query(2013)
    .filter(Movie.rating >= 8.0)
    .filter(Movie.genres.contains("Drama"))
    .all())

# Complex filter conditions (OR, AND, NOT)
condition = (Movie.rating >= 8.0) | (Movie.genres.contains("Sci-Fi"))
movies = Movie.query(2013).filter(condition).all()

# Filter with key condition
results = (Movie.query(2013)
    .starts_with("Inter")
    .filter(Movie.rating < 8.5)
    .all())

# Scan with filters (more expensive but useful)
active_users = User.scan().filter(User.status == "active").all()

# Scan with complex filters
condition = (User.age >= 18) & (User.balance > 0) & User.verified.exists()
eligible_users = User.scan().filter(condition).limit(100).all()

# Use Attr() for dynamic field names
results = User.scan().filter(Attr("custom_field").contains("value")).all()
```

**Filter Operators:**
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`
- String: `.contains()`, `.begins_with()`
- Existence: `.exists()`, `.not_exists()`
- Range: `.between(low, high)`
- Membership: `.is_in([values])`

**Logical Operators:**
- `&` (AND) - Combine multiple conditions
- `|` (OR) - Match any condition
- `~` (NOT) - Negate a condition

#### Mypy Type Checking

> **⚠️ Type Checker Limitation**: Mypy doesn't understand the metaclass DSL (`Movie.rating >= 8.0`) because class attributes are set dynamically at runtime. For mypy-compliant code, use `Attr()` explicitly:

```python
from dynantic import Attr

# ✅ Mypy-safe: Use Attr() explicitly
high_rated = Movie.query(2013).filter(Attr("rating") >= 8.0).all()
drama_movies = Movie.scan().filter(Attr("genres").contains("Drama")).all()

# ❌ Mypy error: Metaclass DSL (works at runtime but mypy complains)
high_rated = Movie.query(2013).filter(Movie.rating >= 8.0).all()
drama_movies = Movie.scan().filter(Movie.genres.contains("Drama")).all()
```

**Why this happens:**
- The DSL (`Movie.rating`) returns `Attr` objects via metaclass magic
- Mypy performs static analysis and doesn't execute metaclass code
- `Attr("rating")` is a regular function call that mypy understands

**When to use `Attr()`:**
- ✅ Always in production code with mypy enabled
- ✅ For optional fields with methods like `.contains()`, `.between()`
- ⚠️ Optional for quick scripts without type checking


> **⚠️ Performance Note**: Filters are applied *after* DynamoDB retrieves items, so you still pay for the read capacity of all scanned items. Use key conditions whenever possible for better performance.

#### Scanning

```python
# Scan all items (expensive!)
for user in User.scan():
    print(user.email)

# Scan with limit
for user in User.scan(limit=100):
    process(user)

# Scan GSI
for order in Order.scan(index_name="status-index"):
    print(order.status)
```

---

### Atomic Updates

**Update DynamoDB items without fetching them first** - saves RCUs and ensures atomicity.

```python
# Atomic counter increment
User.update("user-123", "john@example.com") \
    .add(User.login_count, 1) \
    .execute()

# Multiple actions in one request
User.update("user-123", "john@example.com") \
    .set(User.status, "active") \
    .add(User.balance, 10.50) \
    .add(User.tags, {"verified"}) \
    .remove(User.temporary_code) \
    .execute()

# Conditional update
User.update("user-123", "john@example.com") \\
    .set(User.status, "inactive") \\
    .condition(User.balance < 0) \\
    .execute()

# Delete elements from a set
User.update("user-123", "john@example.com") \\
    .delete(User.permissions, {"admin_access"}) \\
    .execute()

# Return modified attributes
updated_user = User.update("user-123", "john@example.com") \\
    .add(User.login_count, 1) \\
    .return_values("ALL_NEW") \\
    .execute()
```

**Supported Actions:**
- `set(field, value)` - Update an attribute
- `remove(field)` - Remove an attribute
- `add(field, value)` - Increment number or add to set
- `delete(field, value)` - Remove elements from set
- `condition(condition)` - Apply conditional expression
- `return_values(option)` - Control what's returned

---

### Conditional Writes

SQLModel-like DSL for conditional operations:

```python
from dynantic import Attr

# Create-if-not-exists
user = User(user_id="u1", email="test@example.com")
user.save(condition=User.email.not_exists())

# Optimistic locking
user.save(condition=User.version == 5)

# Conditional delete
User.delete("u1", condition=(User.balance == 0) & (User.status == "inactive"))

# Complex conditions
condition = (User.age >= 18) & (User.status == "active") & ~User.is_banned.exists()
user.save(condition=condition)

# Alternative: use Attr() for dynamic field names
User.delete("u1", condition=Attr("legacy_field").not_exists())
```

**Supported Comparisons:**
- `==`, `!=`, `<`, `<=`, `>`, `>=`
- `.exists()`, `.not_exists()`
- `.begins_with(prefix)`
- `.contains(value)`
- `.between(low, high)`
- `.is_in([values])`

**Logical Operators:**
- `&` (AND)
- `|` (OR)
- `~` (NOT)

---

### Batch Operations

**Read and write items in bulk** with automatic chunking and exponential backoff retry.

#### Batch Save

```python
# Save up to thousands of items — auto-chunked into groups of 25
users = [User(user_id=f"u{i}", name=f"User {i}") for i in range(100)]
User.batch_save(users)
```

#### Batch Get

```python
# Fetch multiple items by key — auto-chunked into groups of 100
keys = [{"user_id": f"u{i}"} for i in range(100)]
users = User.batch_get(keys)
# NOTE: DynamoDB does not guarantee order in batch_get responses
```

#### Batch Delete

```python
# Delete multiple items by key — auto-chunked into groups of 25
User.batch_delete([{"user_id": f"u{i}"} for i in range(50)])
```

#### Batch Writer (Context Manager)

```python
# Mix saves and deletes with auto-flush at 25 items
with User.batch_writer() as batch:
    batch.save(User(user_id="u100", name="New User"))
    batch.save(User(user_id="u101", name="Another User"))
    batch.delete(user_id="u1")
    batch.delete(user_id="u2")
```

All batch operations include **exponential backoff retry** for unprocessed items (up to 5 retries). No manual retry logic needed.

---

### Transactions

**ACID transactions** across one or more DynamoDB tables. All operations succeed or all fail.

#### Simple: transact_save

```python
# Atomically save items (can span multiple tables)
user = User(user_id="u1", name="Alice")
order = Order(order_id="o1", amount=99.99)
DynamoModel.transact_save([user, order])
```

#### Advanced: transact_write

```python
from dynantic import Attr, TransactPut, TransactDelete, TransactConditionCheck

DynamoModel.transact_write([
    # Create-if-not-exists
    TransactPut(user, condition=Attr("user_id").not_exists()),
    # Delete with condition
    TransactDelete(Order, condition=Attr("status") == "cancelled", order_id="o1"),
    # Validate without modifying
    TransactConditionCheck(Account, Attr("balance") >= 100, account_id="acc-1"),
])
```

#### Atomic Reads: transact_get

```python
from dynantic import TransactGet

# Get a consistent snapshot of multiple items
results = DynamoModel.transact_get([
    TransactGet(User, user_id="u1"),
    TransactGet(Order, order_id="o1"),
])
# results[0] is User | None, results[1] is Order | None
```

> **Note**: DynamoDB limits transactions to **100 items** per request. Dynantic validates this and raises `ValidationError` if exceeded.

---

### TTL (Time To Live)

**Automatic datetime-to-epoch conversion** for DynamoDB TTL attributes.

```python
from datetime import datetime, timedelta, timezone
from dynantic import DynamoModel, Key, TTL

class Session(DynamoModel):
    session_id: str = Key()
    user_id: str
    expires_at: datetime = TTL()  # Stored as epoch seconds in DynamoDB

    class Meta:
        table_name = "sessions"

# Create with datetime — automatically converted to epoch on save
session = Session(
    session_id="sess-123",
    user_id="user-42",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
)
session.save()

# Read back — automatically converted from epoch to datetime
retrieved = Session.get("sess-123")
print(isinstance(retrieved.expires_at, datetime))  # True
```

**TTL field types:**
- `datetime` — auto-converted to/from epoch seconds (recommended)
- `int` — passed through as raw epoch seconds

TTL works across all write paths: `save()`, `batch_save()`, `batch_writer()`, `transact_save()`, and `transact_write()`.

> **Note**: TTL must also be enabled on the DynamoDB table itself (via Terraform, CDK, or AWS Console). Dynantic only handles the field serialization.

---

### Auto-UUID

**Automatic UUID4 generation** for partition keys and sort keys. No need to manually generate IDs.

```python
from uuid import UUID
from dynantic import DynamoModel, Key

class Product(DynamoModel):
    product_id: UUID = Key(auto=True)  # Auto-generates UUID4
    name: str
    price: float

    class Meta:
        table_name = "products"

# create() — INSERT semantics (fails if PK already exists)
product = Product.create(name="Widget", price=29.99)
print(product.product_id)  # UUID('a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d')
print(type(product.product_id))  # <class 'uuid.UUID'>

# Explicit UUID still works
from uuid import UUID
special = Product.create(product_id=UUID("00000000-..."), name="Promo", price=0.0)

# Duplicate raises ConditionalCheckFailedError
Product.create(product_id=special.product_id, name="Dup", price=0.0)  # Raises!
```

The field type is `UUID` — a native Python type. The serializer handles `UUID → str` for DynamoDB automatically, just like it does for `datetime`, `Enum`, and `Decimal`.

**`create()` vs `save()`:**
- `create()` — INSERT semantics: fails if item already exists (`Attr(pk).not_exists()`)
- `save()` — UPSERT semantics: overwrites if item exists (unchanged behavior)

**Works with all write paths:**
```python
# batch_save — UUID generated at instantiation
products = [Product(name=f"Item {i}", price=i * 10.0) for i in range(100)]
Product.batch_save(products)

# save() after create() works as upsert
product = Product.create(name="Widget", price=29.99)
product.price = 34.99
product.save()  # Updates existing item
```

**`SortKey(auto=True)`** works the same way for composite keys:
```python
from uuid import UUID
from dynantic import DynamoModel, Key, SortKey

class AuditLog(DynamoModel):
    log_id: UUID = Key(auto=True)
    entry_id: UUID = SortKey(auto=True)
    action: str

    class Meta:
        table_name = "audit_logs"
```

> **Note**: Auto-UUID uses Python's `uuid4()` — no external dependencies. UUID4 collision probability is negligible (~1 in 2^122), so no retry logic is needed.

---

### Pagination

**External pagination** lets your API return cursors to clients for stateless pagination.

#### Query Pagination

```python
from dynantic import PageResult

# Get first page
page1 = Order.query("customer-456").limit(10).page()

print(f"Items: {len(page1.items)}, Has more: {page1.has_more}")

# Get next page using cursor
if page1.has_more:
    page2 = Order.query("customer-456").limit(10).page(start_key=page1.last_evaluated_key)
```

#### Scan Pagination

```python
# First page
page1 = Product.scan_page(limit=25)

# Next page
if page1.has_more:
    page2 = Product.scan_page(limit=25, start_key=page1.last_evaluated_key)
```

#### FastAPI Integration

```python
from fastapi import FastAPI, Query
from typing import Any
from pydantic import BaseModel

app = FastAPI()

class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: dict[str, Any] | None
    has_more: bool

@app.get("/orders/{customer_id}")
def get_orders(
    customer_id: str,
    limit: int = Query(default=20, le=100),
    cursor: dict[str, Any] | None = None
) -> PaginatedResponse:
    page = Order.query(customer_id).limit(limit).page(start_key=cursor)
    
    return PaginatedResponse(
        items=[order.model_dump() for order in page.items],
        next_cursor=page.last_evaluated_key,
        has_more=page.has_more
    )
```

---

### Polymorphism

**Single-table design** with automatic type discrimination:

```python
from dynantic import DynamoModel, Key, Discriminator

# 1. Define base table with discriminator
class Animal(DynamoModel):
    animal_id: str = Key()
    name: str
    species: str
    type: str = Discriminator()  # Auto-populated

    class Meta:
        table_name = "animals"

# 2. Register subclasses - discriminator field auto-injected
@Animal.register("DOG")
class Dog(Animal):
    breed: str
    good_boy: bool = True

@Animal.register("CAT")
class Cat(Animal):
    lives_remaining: int = 9
    lazy: bool = True

# Usage
dog = Dog(animal_id="dog-1", name="Buddy", species="dog", breed="Golden Retriever")
cat = Cat(animal_id="cat-1", name="Whiskers", species="cat", lives_remaining=8)

dog.save()
cat.save()

# Scans/queries return correct subclass types
animals = Animal.scan()
for animal in animals:
    if isinstance(animal, Dog):
        print(f"Dog: {animal.name}, Breed: {animal.breed}")
    elif isinstance(animal, Cat):
        print(f"Cat: {animal.name}, Lives: {animal.lives_remaining}")
```

---

## Configuration

### AWS Setup

**Environment Variables:**

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Custom Region in Model:**

```python
class User(DynamoModel):
    user_id: str = Key()
    
    class Meta:
        table_name = "users"
        region = "eu-west-1"  # Override default
```

---

### Boto3 Client Configuration

**Dynantic uses boto3 under the hood.** Configure it for production:

#### Retry Configuration

```python
from botocore.config import Config
import boto3

# Configure retries (boto3 includes built-in retry logic)
config = Config(
    retries={
        'max_attempts': 10,  # Default: 3
        'mode': 'adaptive'   # or 'standard', 'legacy'
    },
    connect_timeout=5,
    read_timeout=10
)

client = boto3.client('dynamodb', config=config)
User.set_client(client)
```

**Retry Modes:**
- `standard`: Fixed delays with exponential backoff
- `adaptive`: Adjusts retry rate based on throttling
- `legacy`: Old boto behavior (not recommended)

#### Connection Pooling

```python
config = Config(
    max_pool_connections=50  # Default: 10
)
```

#### Client Lifecycle Management

**For Global Singleton** (Lambda, scripts):

```python
import boto3
from dynantic import DynamoModel

# Create once at module level
dynamo_client = boto3.client('dynamodb')
DynamoModel.set_client(dynamo_client)
```

**For Per-Request Clients** (multi-tenant):

```python
from dynantic import DynamoModel

# Context manager for scoped client
with User.using_client(tenant_specific_client):
    user = User.get("user-123")
```

#### Testing with Mocks

```python
import pytest
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_dynamo_client():
    client = MagicMock()
    client.get_item.return_value = {
        'Item': {
            'user_id': {'S': 'test-123'},
            'email': {'S': 'test@example.com'}
        }
    }
    return client

def test_user_get(mock_dynamo_client):
    User.set_client(mock_dynamo_client)
    user = User.get("test-123")
    
    assert user.user_id == "test-123"
    mock_dynamo_client.get_item.assert_called_once()
```

#### Dependency Injection Pattern (Recommended)

```python
from contextlib import contextmanager
import boto3

@contextmanager
def dynamo_client():
    \"\"\"Context manager for boto3 client lifecycle.\"\"\"
    client = boto3.client('dynamodb')
    try:
        yield client
    finally:
        # Boto3 clients don't need explicit cleanup  
        # (but you can add custom teardown logic here)
        pass

# Use it
with dynamo_client() as client:
    User.set_client(client)
    user = User.get("user-123")
```

---

### Testing with LocalStack

**docker-compose.yaml:**

```yaml
version: '3.8'
services:
  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=dynamodb
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
    volumes:
      - "/tmp/localstack:/tmp/localstack"
```

**pytest conftest.py:**

```python
import boto3
import pytest
import os

@pytest.fixture(scope="session", autouse=True)
def localstack_setup():
    os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    
@pytest.fixture
def dynamo_client():
    return boto3.client("dynamodb", endpoint_url="http://localhost:4566")

@pytest.fixture
def create_test_table(dynamo_client):
    dynamo_client.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "email", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    yield
    dynamo_client.delete_table(TableName="users")
```

---

## Async Usage

**Dynantic is sync-first** for Lambda/serverless optimization. For async frameworks:

### FastAPI with Thread Pool

```python
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    # Run sync code in thread pool
    return await asyncio.to_thread(User.get, user_id)

@app.post("/users")
async def create_user(user_data: dict):
    user = User(**user_data)
    await asyncio.to_thread(user.save)
    return user.model_dump()
```

### Why Not Native Async?

1. **Cold Start Overhead**: Async runtimes have higher initialization cost
2. **Complexity**: Most DynamoDB operations don't benefit from concurrency
3. **Lambda Fit**: AWS Lambda is optimized for sync request/response
4. **Future**: `aioboto3` support may be added if demand exists

**Alternative**: Use [aiobotocore](https://github.com/aio-libs/aiobotocore) or [aioboto3](https://github.com/terrycain/aioboto3) directly if you need native async.

---

## Limitations

### Current Limitations

| Feature | Status | Notes |
|---------|--------|-------|
| Batch operations | ✅ **v0.3.0** | `batch_get`, `batch_save`, `batch_delete`, `batch_writer` |
| Transactions | ✅ **v0.3.0** | `transact_save`, `transact_write`, `transact_get` |
| TTL fields | ✅ **v0.3.0** | Automatic datetime/epoch conversion with `TTL()` |
| Auto-UUID | ✅ **v0.3.0** | `Key(auto=True)` + `create()` with INSERT semantics |
| Async support | ❌ Not planned | Use `asyncio.to_thread()` or aioboto3 directly |
| Streams | ❌ Not planned | Use AWS Lambda triggers |
| PartiQL queries | ❌ Not planned | Use standard query API |
| Auto-migrations | ❌ Not planned | Manage tables with IaC (Terraform, CDK) |

### Design Constraints

- **No Relationships**: DynamoDB doesn't support joins
- **No Schema Enforcement**: DynamoDB is schemaless (Pydantic validates on read/write)
- **No OR Queries**: DynamoDB limitations (use GSI or client-side filtering)
- **Cursor Opacity**: Pagination cursors are plain dicts (not cryptographically signed)

---

## Security Considerations

### 1. Pagination Cursors

**Risk**: Cursors are unencrypted Python dicts that clients can tamper with.

**Mitigation**:
- Always re-apply authorization checks server-side
- Validate cursor fields before use
- Consider signing cursors for high-security applications

**Example**:
```python
# Bad: Trusting cursor without validation
@app.get("/orders")
def get_orders(cursor: dict | None):
    return Order.scan_page(start_key=cursor)  # ❌ Unsafe!

# Good: Re-apply authorization
@app.get("/orders")
def get_orders(current_user: User, cursor: dict | None):
    # Always filter by authenticated user
    return Order.query(current_user.user_id).page(start_key=cursor)  # ✅ Safe
```

### 2. Conditional Expressions

**Risk**: SQL-injection-like attacks if field names come from user input.

**Mitigation**:
- Never pass raw user input to `Attr(user_input)`
- Use model field references: `User.email` instead of `Attr("email")`
- Dynantic uses `ExpressionAttributeNames` to prevent injection

```python
# Bad: User controls field name
field_name = request.query_params.get("field")  # ❌ Dangerous!
condition = Attr(field_name).exists()

# Good: Use model fields
condition = User.email.exists()  # ✅ Safe
```

### 3. PII in Logs

**Default Behavior**: Dynantic redacts keys in logs (SHA256 hash, first 8 chars).

**Warning**: Debug logs may contain attribute values.

**Recommendation**:
```python
import logging
logging.getLogger("dynantic").setLevel(logging.INFO)  # Not DEBUG
```

### 4. IAM Permissions

**Minimum Required Permissions**:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem"
    ],
    "Resource": "arn:aws:dynamodb:*:*:table/your-table-name"
  }]
}
```

**With GSI**:
```json
{
  "Resource": [
    "arn:aws:dynamodb:*:*:table/your-table-name",
    "arn:aws:dynamodb:*:*:table/your-table-name/index/*"
  ]
}
```

---

## Performance Tips

### 1. Use Projections for Large Items

```python
# Only fetch needed attributes (not yet supported - coming soon)
# Workaround: Use boto3 directly for now
```

### 2. Prefer Query Over Scan

```python
# Bad: Full table scan
all_orders = list(Order.scan())  # ❌ Expensive!

# Good: Query with partition key
customer_orders = Order.query("customer-456").all()  # ✅ Efficient
```

### 3. Use Batch Operations

```python
# Bad: Loop over individual gets
for user_id in user_ids:
    user = User.get(user_id)  # ❌ N round-trips

# Good: Batch get (1 call per 100 keys, with retry)
users = User.batch_get([{"user_id": uid} for uid in user_ids])  # ✅
```

### 4. Configure Boto3 Connection Pool

```python
config = Config(max_pool_connections=50)  # Default: 10
client = boto3.client('dynamodb', config=config)
```

### 5. Monitor Read/Write Capacity

- Use DynamoDB on-demand billing for variable workloads
- Monitor `ProvisionedThroughputExceededError` errors
- Implement exponential backoff (boto3 does this automatically)

---

## Comparison with Alternatives

| Feature | Dynantic | PynamoDB | Boto3 (Resource/Client) |
|---------|----------|----------|-------------------------|
| Type Safety | ✅ Pydantic v2 | ⚠️ Custom types | ❌ Dict-based |
| IDE Autocomplete | ✅ Excellent | ✅ Good | ❌ Limited |
| Query DSL | ✅ Pythonic | ✅ Pythonic | ❌ Dict-based |
| Async Support | ❌ Sync only | ❌ Sync only | ❌ Sync (use aioboto3 separately) |
| Batch Ops | ✅ Yes | ✅ Yes | ✅ Yes |
| Transactions | ✅ Yes | ✅ Yes | ✅ Yes |
| TTL Support | ✅ Auto-convert | ✅ Yes | ❌ Manual |
| Learning Curve | ⚠️ Medium | ⚠️ Medium | ❌ Steep |
| Maturity | ⚠️ Beta | ✅ Stable | ✅ AWS Official |

**When to use Dynantic:**
- You love Pydantic and want DynamoDB integration
- You're building Lambda functions or sync applications
- You want excellent IDE support with Pydantic validation
- You're okay using a newer library (beta status)

**When to use PynamoDB:**
- You want a mature, battle-tested library
- You prefer a custom type system over Pydantic
- You don't need Pydantic's validation features

**When to use raw boto3:**
- You need maximum control and flexibility
- You're optimizing for absolute performance
- You have simple use cases
- You want AWS's official SDK with guaranteed compatibility

**When to use aioboto3:**
- You need native async/await support
- You're building async applications (aiohttp, FastAPI with async endpoints)
- You're willing to manage async client lifecycle

---

## Contributing

We welcome contributions! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`uv run pytest`)
5. Run type checking (`uv run mypy dynantic`)
6. Run linting (`uv run ruff check dynantic`)
7. Submit a pull request

**Development Setup:**

```bash
git clone https://github.com/Simi24/dynantic.git
cd dynantic
uv sync  # Install dependencies
docker compose up -d  # Start LocalStack
uv run pytest  # Run tests
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by [SQLModel](https://sqlmodel.tiangolo.com/) and [PynamoDB](https://github.com/pynamodb/PynamoDB)
- Built on [Pydantic](https://docs.pydantic.dev/) and [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- Thanks to all contributors!

---

## Support

- 📖 **Documentation**: This README
- 📧 **Email**: pettasimonepaolo@gmail.com

---

**Made with ❤️ for the Python and DynamoDB community**