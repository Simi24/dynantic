---
name: dynantic
description: "Use this skill when the user explicitly asks to use dynantic or when you see `from dynantic import` in existing code. Dynantic is a type-safe DynamoDB ORM built on Pydantic v2. This skill covers model definition, CRUD operations, querying, filtering, pagination, conditional writes, atomic updates, batch operations, ACID transactions, TTL fields, auto-UUID keys, polymorphism (single-table design), and FastAPI integration patterns. Do NOT trigger this skill for general DynamoDB questions — only when dynantic is specifically mentioned or already in use in the codebase."
---

# Dynantic — Type-Safe DynamoDB ORM

Dynantic wraps boto3's low-level DynamoDB client with Pydantic v2 validation. It's synchronous-first, designed for AWS Lambda and FastAPI.

**Install:** `pip install dynantic`
**Requires:** Python 3.10+, pydantic >= 2.6.0, boto3 >= 1.34.0

---

## Model Definition

Every model extends `DynamoModel` and declares a `Meta` with `table_name`. Use `Key()` for partition key, `SortKey()` for optional sort key.

```python
from datetime import datetime
from decimal import Decimal

from pydantic import EmailStr

from dynantic import DynamoModel, Key, SortKey

class User(DynamoModel):
    email: str = Key()
    created_at: str = SortKey()
    name: str
    age: int
    balance: Decimal = Decimal("0")
    tags: set[str] = set()
    verified: bool = False

    class Meta:
        table_name = "users"
        region = "eu-west-1"  # Optional, defaults to us-east-1
```

Dynantic does NOT create tables or manage schema migrations — use Terraform, CDK, or `awslocal` for that. The model defines how Python interacts with an existing table.

### Field Types

| Python Type | DynamoDB Type | Notes |
|------------|---------------|-------|
| `str` | S | |
| `int`, `float`, `Decimal` | N | Use `Decimal` for money |
| `bool` | BOOL | |
| `bytes` | B | |
| `datetime`, `date` | S | ISO 8601 string |
| `UUID` | S | String representation |
| `Enum` | S | Uses `.value` |
| `list[T]` | L | Nested types supported |
| `dict[str, T]` | M | Map type |
| `set[str]` | SS | String set |
| `set[int]` | NS | Number set |

### Key Fields

```python
from dynantic import Key, SortKey, GSIKey, GSISortKey, Discriminator, TTL

class MyModel(DynamoModel):
    pk: str = Key()                                    # Partition key (exactly 1 required)
    sk: str = SortKey()                                # Sort key (0 or 1)
    gsi_pk: str = GSIKey(index_name="MyIndex")         # GSI partition key
    gsi_sk: str = GSISortKey(index_name="MyIndex")     # GSI sort key
    entity_type: str = Discriminator()                 # For polymorphism (single-table)
    expires_at: datetime = TTL()                       # TTL field (auto epoch conversion)
```

You can define multiple GSIs by using different `index_name` values. Each GSI needs its own GSIKey and optionally a GSISortKey.

### Auto-UUID Keys

Use `Key(auto=True)` or `SortKey(auto=True)` to auto-generate UUID4 values on instantiation. The field should be typed as `UUID`.

```python
from uuid import UUID

from dynantic import DynamoModel, Key, SortKey

class Product(DynamoModel):
    product_id: UUID = Key(auto=True)
    name: str
    price: float

    class Meta:
        table_name = "products"

class AuditLog(DynamoModel):
    log_id: UUID = Key(auto=True)
    entry_id: UUID = SortKey(auto=True)
    action: str

    class Meta:
        table_name = "audit_logs"
```

Auto-UUID works with all write paths: `save()`, `create()`, `batch_save()`, `transact_save()`.

### TTL (Time To Live) Fields

Mark a field with `TTL()` to enable automatic DynamoDB TTL handling. Use `datetime` (recommended, auto-converted to epoch seconds on save and back on read) or `int` (raw epoch, passed through as-is).

```python
from datetime import datetime, timedelta, timezone

from dynantic import TTL, DynamoModel, Key

class Session(DynamoModel):
    session_id: str = Key()
    user_id: str
    expires_at: datetime = TTL()

    class Meta:
        table_name = "sessions"

# Create a session that expires in 24 hours
session = Session(
    session_id="sess-abc123",
    user_id="user-42",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
)
session.save()
# DynamoDB stores expires_at as N (epoch seconds): {"N": "1750000000"}

# Read it back — automatically deserialized to datetime
retrieved = Session.get("sess-abc123")
print(isinstance(retrieved.expires_at, datetime))  # True
```

TTL serialization works across all write paths: `save()`, `batch_save()`, `batch_writer()`, `transact_save()`.

TTL must also be enabled on the DynamoDB table itself (via Terraform/CLI) — dynantic only handles the serialization.

---

## CRUD Operations

### Create (INSERT Semantics)

`create()` instantiates and saves with a condition that the PK must not exist — true INSERT behavior. Ideal with auto-UUID keys.

```python
# With auto-UUID: PK is generated automatically
product = Product.create(name="Widget", price=29.99)
print(product.product_id)  # UUID object, auto-generated

# With explicit PK
user = User.create(email="test@example.com", created_at="2024-01-01", name="Test", age=25)

# Fails if key already exists
try:
    Product.create(product_id=existing_id, name="Duplicate", price=0.0)
except ConditionalCheckFailedError:
    print("Duplicate blocked")
```

### Save (Create / Overwrite)

```python
user = User(email="alice@example.com", created_at="2024-01-01", name="Alice", age=30)
user.save()

# Create-if-not-exists (conditional write)
user.save(condition=Attr("email").not_exists())
```

`save()` does a full PutItem — it overwrites if the key already exists unless you add a condition.

### Get (Single Item)

```python
# Table with partition key only
user = User.get("alice@example.com")

# Table with partition + sort key
user = User.get("alice@example.com", "2024-01-01")

# Returns None if not found
if user is None:
    print("Not found")
```

### Delete

```python
# Class method — delete by key
User.delete("alice@example.com", "2024-01-01")

# With condition
User.delete("alice@example.com", "2024-01-01", condition=Attr("status") == "inactive")

# Instance method — delete current object
user.delete_item()
user.delete_item(condition=Attr("version") == 3)
```

---

## Query Builder

Queries require a partition key value. Sort key conditions and filters are optional. Queries are lazy — nothing hits DynamoDB until you call a terminal method.

```python
# All items for a partition key
orders = Order.query("user-123").all()

# Sort key conditions (fluent chain)
recent = Order.query("user-123").gt("2024-01-01").all()
range_ = Order.query("user-123").between("2024-01-01", "2024-12-31").all()
prefix = Order.query("user-123").starts_with("2024-").all()

# Reverse order (descending sort key)
latest = Order.query("user-123").reverse().first()

# Limit
top5 = Order.query("user-123").reverse().limit(5).all()
```

### Sort Key Condition Methods

These are called directly on the query builder after `.query(pk)`:

| Method | DynamoDB Expression |
|--------|-------------------|
| `.eq(value)` | `SK = :val` |
| `.ne(value)` | `SK <> :val` |
| `.gt(value)` | `SK > :val` |
| `.ge(value)` | `SK >= :val` |
| `.lt(value)` | `SK < :val` |
| `.le(value)` | `SK <= :val` |
| `.between(low, high)` | `SK BETWEEN :low AND :high` |
| `.starts_with(prefix)` | `begins_with(SK, :prefix)` |

### Terminal Methods

| Method | Returns | Behavior |
|--------|---------|----------|
| `.all()` | `list[T]` | All matching items (auto-paginates) |
| `.first()` | `T \| None` | First match or None |
| `.one()` | `T` | Exactly one match, raises if 0 or >1 |
| `.page(start_key=None)` | `PageResult[T]` | Single page with cursor |
| `for item in query:` | `T` | Lazy iteration with auto-pagination |

### Filtering (Post-Query)

Filters run after DynamoDB retrieves items — you still pay RCUs for all scanned items. Use key conditions for efficiency, filters for refinement.

```python
from dynantic import Attr

# Single filter
premium = User.query("org-1").filter(Attr("tier") == "premium").all()

# Multiple filters (AND-combined)
results = (Order.query("user-1")
    .gt("2024-01-01")
    .filter(Attr("status") == "shipped")
    .filter(Attr("total") > 100)
    .all())

# Complex conditions with logical operators
condition = (Attr("rating") >= 4.0) | (Attr("featured") == True)
movies = Movie.query(2024).filter(condition).all()
```

---

## Conditions DSL

`Attr()` builds conditions for both filter expressions and conditional writes.

```python
from dynantic import Attr

# Comparison operators
Attr("age") == 30        # equals
Attr("age") != 30        # not equals
Attr("age") > 18         # greater than
Attr("age") >= 18        # greater or equal
Attr("age") < 65         # less than
Attr("age") <= 65        # less or equal

# Existence checks
Attr("email").exists()       # attribute_exists
Attr("temp").not_exists()    # attribute_not_exists

# String / set operations
Attr("name").begins_with("A")   # begins_with
Attr("tags").contains("vip")    # contains (works on strings and sets)
Attr("age").between(18, 65)     # BETWEEN
Attr("status").is_in(["active", "pending"])  # IN

# Logical operators
(Attr("age") >= 18) & (Attr("status") == "active")  # AND
(Attr("tier") == "gold") | (Attr("tier") == "platinum")  # OR
~Attr("banned").exists()  # NOT
```

### Operator equivalents

`Attr` also provides named method equivalents: `.eq()`, `.ne()`, `.gt()`, `.gte()`, `.lt()`, `.lte()`.

---

## Atomic Updates

Update items without fetching them first. Saves RCUs and avoids race conditions.

```python
# Start from class method (by key)
User.update("alice@example.com", "2024-01-01") \
    .set(User.name, "Alice Smith") \
    .execute()

# Start from instance
user.patch() \
    .set(User.name, "Alice Smith") \
    .execute()
```

### Update Actions

```python
builder = User.update("alice@example.com", "2024-01-01")

# SET — overwrite a field
builder.set(User.name, "New Name")

# ADD — increment number or add to set
builder.add(User.login_count, 1)
builder.add(User.tags, {"new-tag"})

# REMOVE — delete a field
builder.remove(User.temp_field)

# DELETE — remove elements from a set
builder.delete(User.tags, {"old-tag"})
```

### Chaining & Options

```python
updated = User.update("alice@example.com", "2024-01-01") \
    .set(User.status, "verified") \
    .add(User.login_count, 1) \
    .remove(User.temp_code) \
    .condition(Attr("version") == 5)          # Conditional update
    .return_values("ALL_NEW")                 # Get updated item back
    .execute()                                # Returns model instance when ALL_NEW
```

`return_values` options: `"NONE"`, `"ALL_OLD"`, `"UPDATED_OLD"`, `"ALL_NEW"`, `"UPDATED_NEW"`.

---

## Batch Operations

Batch operations handle auto-chunking (25 for writes, 100 for reads) and retry unprocessed items with exponential backoff — no manual retry logic needed.

### batch_save

```python
# Save 50 users in one call (auto-chunks into 2 batches of 25)
users = [User(user_id=f"u{i}", name=f"User {i}", email=f"u{i}@test.com", age=20+i) for i in range(50)]
User.batch_save(users)
```

### batch_get

```python
# Fetch multiple items by key (auto-chunks into groups of 100)
keys = [{"user_id": f"u{i}"} for i in range(50)]
users = User.batch_get(keys)

# NOTE: DynamoDB does not guarantee order in batch_get responses.
# Sort after fetching if you need ordered results.
sorted_users = sorted(users, key=lambda u: u.user_id)
```

### batch_delete

```python
# Delete multiple items by key (auto-chunks at 25)
keys = [{"user_id": f"u{i}"} for i in range(25)]
User.batch_delete(keys)
```

### batch_writer (Context Manager)

Mix saves and deletes in a single batch context. Auto-flushes every 25 items and on context exit. Does not flush on exception.

```python
with User.batch_writer() as batch:
    # Add new items
    for i in range(100):
        batch.save(User(user_id=f"u{i}", name=f"User {i}", email=f"u{i}@test.com", age=25))

    # Delete existing items
    for i in range(200, 210):
        batch.delete(user_id=f"u{i}")
```

---

## Transactions

ACID transactions across one or multiple DynamoDB tables. Limited to 100 items per transaction (DynamoDB constraint). Dynantic validates this limit and raises `ValidationError` if exceeded.

### transact_save (Simple)

Atomically saves multiple items. All succeed or all fail. Works across different model classes (cross-table).

```python
from dynantic import DynamoModel

alice = Account(account_id="acc-1", owner="Alice", balance=1000.0)
bob = Account(account_id="acc-2", owner="Bob", balance=500.0)
transfer = Transfer(transfer_id="tx-001", from_account="acc-1", to_account="acc-2", amount=200.0)

# All three saved atomically, even though Account and Transfer are different tables
DynamoModel.transact_save([alice, bob, transfer])
```

### transact_write (Advanced)

Supports mixed actions: `TransactPut`, `TransactDelete`, `TransactConditionCheck`.

```python
from dynantic import Attr, DynamoModel, TransactPut, TransactDelete, TransactConditionCheck

# Bank transfer: update balances + record transfer + verify sender is active
DynamoModel.transact_write([
    TransactPut(
        Account(account_id="acc-1", owner="Alice", balance=800.0),
        condition=(Attr("active") == True) & (Attr("balance") >= 200),
    ),
    TransactPut(Account(account_id="acc-2", owner="Bob", balance=700.0)),
    TransactPut(transfer),
    TransactDelete(
        OldRecord,
        condition=Attr("status") == "archived",
        record_id="old-001",
    ),
])
```

**TransactConditionCheck** asserts a condition on an item without modifying it — useful for cross-item validation:

```python
DynamoModel.transact_write([
    TransactPut(new_order),
    # Verify the user is active before creating the order (no write to User)
    TransactConditionCheck(User, Attr("status").eq("active"), user_id="u1"),
])
```

### transact_get (Consistent Reads)

Atomically reads multiple items for a consistent snapshot.

```python
from dynantic import DynamoModel, TransactGet

results = DynamoModel.transact_get([
    TransactGet(Account, account_id="acc-1"),
    TransactGet(Account, account_id="acc-2"),
    TransactGet(Transfer, transfer_id="tx-001"),
])

# Results are in the same order as the input actions
alice, bob, transfer = results

# Missing items return None
if alice is None:
    print("Account not found")
```

---

## Scanning

Full-table scans are expensive but sometimes necessary. Same filter/terminal API as queries.

```python
# Scan entire table
all_users = User.scan().all()

# With filter
active = User.scan().filter(Attr("status") == "active").all()

# Scan a GSI
User.scan(index_name="StatusIndex").filter(Attr("status") == "active").all()

# Paginated scan
page = User.scan().limit(50).page()
```

---

## GSI Queries

Define GSI fields in your model, then query them with `query_index()`.

```python
class Employee(DynamoModel):
    employee_id: str = Key()
    name: str
    department: str = GSIKey(index_name="DepartmentIndex")
    hire_date: str = GSISortKey(index_name="DepartmentIndex")
    location: str = GSIKey(index_name="LocationIndex")

    class Meta:
        table_name = "employees"

# Query by department, sorted by hire date
engineers = Employee.query_index("DepartmentIndex", "Engineering") \
    .gt("2024-01-01") \
    .all()

# Query by location
sf_employees = Employee.query_index("LocationIndex", "San Francisco").all()
```

The GSI must exist on the actual DynamoDB table — dynantic doesn't create it.

---

## Pagination

For stateless APIs (REST/GraphQL), use `.page()` to get one page at a time with a cursor.

```python
from dynantic import PageResult

# First page
page: PageResult[Order] = Order.query("user-1").limit(20).page()
# page.items        -> list[Order]
# page.has_more     -> bool
# page.last_evaluated_key -> dict | None (cursor for next page)
# page.count        -> int

# Next page
if page.has_more:
    page2 = Order.query("user-1").limit(20).page(start_key=page.last_evaluated_key)
```

Also works with `scan()`:
```python
page = User.scan().limit(50).page()
page = User.scan().limit(50).page(start_key=page.last_evaluated_key)
```

---

## Client Management

Dynantic uses a global singleton boto3 client by default. Override it for testing or custom configuration.

```python
import boto3
from botocore.config import Config

from dynantic import DynamoModel

# Custom client (e.g., LocalStack)
client = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:4566",
    region_name="eu-west-1",
)
DynamoModel.set_client(client)

# Scoped client (context manager)
with User.using_client(test_client):
    user = User.get("test-key")  # Uses test_client only within this block
```

---

## Exception Handling

```python
from dynantic.exceptions import (
    ConditionalCheckFailedError,
    TableNotFoundError,
    TransactionConflictError,
    ProvisionedThroughputExceededError,
    ValidationError,
)

try:
    user.save(condition=Attr("version") == expected)
except ConditionalCheckFailedError:
    # Optimistic lock failed — someone else modified the item
    pass
except TableNotFoundError:
    # Table doesn't exist
    pass

try:
    DynamoModel.transact_write([...])
except TransactionConflictError:
    # Transaction conflicts with another ongoing transaction, or a condition failed
    pass
```

All exceptions inherit from `DynanticError` and carry the `original_error` (the underlying `ClientError`).

---

## Logging

```python
import logging

# Enable debug logging (shows DynamoDB requests, keys are redacted)
logging.getLogger("dynantic").setLevel(logging.DEBUG)

# INFO level in production (hides PII)
logging.getLogger("dynantic").setLevel(logging.INFO)
```

---

## Common Pitfalls

1. **Empty sets** — DynamoDB doesn't allow empty sets. Don't save `set()`. Use `None` or omit the field.
2. **Float precision** — Use `Decimal` for financial values, not `float`.
3. **Filter != Key condition** — Filters don't reduce RCU cost. Design your keys for your access patterns.
4. **save() overwrites** — It's a PutItem. Use `condition=Attr("pk").not_exists()` for create-only, or use `create()`.
5. **Table must exist** — Dynantic doesn't create tables. Use Terraform or `awslocal`.
6. **Async** — Dynantic is synchronous. In FastAPI, wrap with `asyncio.to_thread()` or use sync endpoints.
7. **batch_get order** — DynamoDB does not guarantee order in batch_get responses. Sort after fetching if needed.
8. **Transaction limits** — Max 100 items per transaction. Dynantic validates this and raises `ValidationError`.

---

## Advanced Patterns

For polymorphism (single-table design), FastAPI integration, and testing patterns, read `references/advanced-patterns.md`.

For a compact API reference table, read `references/api-quick-ref.md`.
