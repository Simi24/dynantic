<div align="center" markdown>

![Dynantic](assets/dyno_dynantic.png){ width="400" }

# Dynantic

**Type-safe DynamoDB ORM with Pydantic validation**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/dynantic)](https://pypi.org/project/dynantic/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

</div>

---

Dynantic is a **synchronous-first** Python ORM for Amazon DynamoDB that combines Pydantic v2 validation with an elegant query DSL.

## Features

- :white_check_mark: **Pydantic v2** validation and type safety
- :white_check_mark: **Metaclass-based DSL** for elegant query building
- :white_check_mark: **Comprehensive type support** — datetime, UUID, Enum, Decimal, sets, and more
- :white_check_mark: **Global Secondary Indexes** (GSI)
- :white_check_mark: **Polymorphic models** for single-table design
- :white_check_mark: **Conditional writes** with SQLModel-like syntax
- :white_check_mark: **Atomic updates** without fetching first
- :white_check_mark: **External pagination** for stateless APIs
- :white_check_mark: **Batch operations** with auto-chunking and retry
- :white_check_mark: **ACID transactions** across tables
- :white_check_mark: **TTL support** with automatic datetime/epoch conversion
- :white_check_mark: **Auto-UUID** with `Key(auto=True)` and INSERT-safe `create()`

**Optimized for**: AWS Lambda, serverless functions, FastAPI (with threadpool), batch jobs, and scripts.

## Installation

```bash
pip install dynantic
```

**Requirements:** Python 3.10+ · pydantic >= 2.6.0 · boto3 >= 1.34.0

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

## Why Dynantic?

| | **Dynantic** | **PynamoDB** | **Raw boto3** |
|---|:---:|:---:|:---:|
| Pydantic v2 validation | :white_check_mark: | :x: | :x: |
| Type-safe queries | :white_check_mark: | :white_check_mark: | :x: |
| IDE autocomplete | :white_check_mark: | Partial | :x: |
| Lambda-optimized (sync) | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Batch + Transactions | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Polymorphism | :white_check_mark: | :x: | :x: |
| Learning curve | Low | Medium | High |

!!! warning "Beta Software"
    Dynantic is in active development. The API is stable, but you may encounter rough edges. Production use is at your own risk. Feedback and contributions are welcome!
