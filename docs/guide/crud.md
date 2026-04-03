# CRUD Operations

## Create / Save

```python
product = Product(
    product_id="prod-123",
    name="Widget",
    price=29.99,
    in_stock=True
)
product.save()
```

### Create with Condition (Insert-if-not-exists)

```python
product.save(condition=Product.product_id.not_exists())
```

This raises `ConditionalCheckFailedError` if the item already exists.

### INSERT Semantics with `create()`

For models with [Auto-UUID](auto-uuid.md) keys, `create()` guarantees insert-only semantics:

```python
class Task(DynamoModel):
    task_id: str = Key(auto=True)
    title: str

    class Meta:
        table_name = "tasks"

task = Task(title="Buy groceries")
task.create()  # Generates UUID and saves with condition check
```

## Read / Get

```python
# By partition key only
product = Product.get("prod-123")

# By partition + sort key
order = Order.get("customer-456", "order-789")

# Returns None if not found (no exception)
missing = Product.get("nonexistent")  # None
```

!!! info
    `get()` always returns `None` for missing items — never raises an exception.

## Update

### Fetch-then-save

```python
product = Product.get("prod-123")
product.price = 34.99
product.save()
```

### Atomic updates (no fetch required)

For atomic, server-side updates without a round-trip, see [Atomic Updates](updates.md).

```python
Product.update("prod-123") \
    .set(Product.price, 34.99) \
    .execute()
```

## Delete

```python
# By key (no fetch required)
Product.delete("prod-123")

# From instance
product = Product.get("prod-123")
product.delete_item()

# With condition
Product.delete("prod-123", condition=Product.in_stock == False)
```
