# Auto-UUID

Automatic UUID4 generation for partition keys and sort keys.

## Basic Usage

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
print(product.product_id)  # UUID('a1b2c3d4-e5f6-...')
print(type(product.product_id))  # <class 'uuid.UUID'>
```

## `create()` vs `save()`

| Method | Semantics | Behavior on duplicate |
|---|---|---|
| `create()` | INSERT | Raises `ConditionalCheckFailedError` |
| `save()` | UPSERT | Overwrites existing item |

```python
# create() adds a condition: Attr(pk).not_exists()
product = Product.create(name="Widget", price=29.99)

# save() after create() works as upsert
product.price = 34.99
product.save()  # Updates existing item
```

## Explicit UUID Override

```python
from uuid import UUID

explicit_id = UUID("00000000-0000-4000-8000-000000000001")
special = Product.create(product_id=explicit_id, name="Promo", price=0.0)
```

## Composite Key with Auto-UUID

Both partition key and sort key can use `auto=True`:

```python
from uuid import UUID
from dynantic import DynamoModel, Key, SortKey

class AuditLog(DynamoModel):
    log_id: UUID = Key(auto=True)
    entry_id: UUID = SortKey(auto=True)
    action: str
    details: str = ""

    class Meta:
        table_name = "audit_logs"

log = AuditLog.create(action="USER_LOGIN", details="From 192.168.1.1")
print(f"pk={log.log_id}, sk={log.entry_id}")
```

## Works with All Write Paths

UUID is generated at **instantiation time**, so it works with batch operations:

```python
products = [Product(name=f"Item {i}", price=i * 10.0) for i in range(100)]
Product.batch_save(products)
# Each product has a unique UUID assigned at creation
```

!!! note
    Auto-UUID uses Python's `uuid4()` — no external dependencies. UUID4 collision probability is negligible (~1 in 2^122).
