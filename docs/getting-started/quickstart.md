# Quick Start

This guide walks you from zero to your first DynamoDB operations with Dynantic.

## Define a Model

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
```

Every model extends `DynamoModel` and declares a `Meta` class with the `table_name`. Fields marked with `Key()` and `SortKey()` form the primary key.

!!! note "Table Creation"
    Dynantic does **not** create tables automatically. Use Terraform, CDK, or the AWS Console to create the table before running your code.

## Create an Item

```python
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
```

Pydantic validates all fields before saving. Invalid data raises a `ValidationError` immediately.

## Read an Item

```python
user = User.get("user-123", "john@example.com")
print(f"User: {user.name}, Status: {user.status.value}")
```

`get()` returns `None` if the item doesn't exist — no exceptions.

## Update (Atomic)

```python
User.update("user-123", "john@example.com") \
    .add(User.balance, 10.0) \
    .add(User.tags, {"early_adopter"}) \
    .execute()
```

Atomic updates modify items **without fetching them first**, saving read capacity and ensuring atomicity.

## Delete

```python
User.delete("user-123", "john@example.com")
```

## Query

```python
# All items for a partition key
users = User.query("user-123").all()

# With sort key condition
user = User.query("user-123").eq("john@example.com").first()
```

## What's Next?

- [Model Definition](../guide/models.md) — Field types, GSIs, type support
- [CRUD Operations](../guide/crud.md) — Full create/read/update/delete guide
- [Querying](../guide/querying.md) — Sort key conditions, filtering, scanning
- **Atomic Updates** — Update without fetching
