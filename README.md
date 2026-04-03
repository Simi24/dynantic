<p align="center">
    <img src="assets/dyno_dynantic.png" alt="Dynantic" width="600" />
</p>

# Dynantic

**Type-safe DynamoDB ORM with Pydantic validation**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/dynantic)](https://pypi.org/project/dynantic/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

> **[Read the Documentation](https://simi24.github.io/dynantic)**

---

Dynantic is a **synchronous-first** Python ORM for Amazon DynamoDB that combines Pydantic v2 validation with an elegant query DSL.

## Features

- Pydantic v2 validation and type safety
- Metaclass-based DSL for elegant query building
- Comprehensive type support (datetime, UUID, Enum, Decimal, sets, etc.)
- Global Secondary Indexes (GSI)
- Polymorphic models for single-table design
- Conditional writes with SQLModel-like syntax
- Atomic updates without fetching first
- Batch operations with auto-chunking and retry
- ACID transactions across tables
- TTL support with automatic datetime/epoch conversion
- Auto-UUID with `Key(auto=True)` and INSERT-safe `create()`

**Optimized for**: AWS Lambda, serverless functions, FastAPI, batch jobs, and scripts.

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

# Update (atomic)
User.update("user-123", "john@example.com") \
    .add(User.balance, 10.0) \
    .execute()

# Delete
User.delete("user-123", "john@example.com")
```

> **[Full documentation and guides](https://simi24.github.io/dynantic)**

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests and ensure they pass (`uv run pytest`)
4. Run type checking (`uv run mypy dynantic`)
5. Submit a pull request

```bash
git clone https://github.com/Simi24/dynantic.git
cd dynantic
uv sync --dev
docker compose up -d  # Start LocalStack
uv run pytest
```

## License

MIT License - see [LICENSE](LICENSE) for details.
