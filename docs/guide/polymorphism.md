# Polymorphism (Single-Table Design)

Automatic type discrimination for single-table design patterns.

## Define the Base Model

```python
from dynantic import DynamoModel, Key, SortKey, Discriminator

class Entity(DynamoModel):
    pk: str = Key()
    sk: str = SortKey()
    entity_type: str = Discriminator()  # Auto-populated with registered value

    class Meta:
        table_name = "SingleTableExample"
```

## Register Subclasses

```python
@Entity.register("CUSTOMER")
class Customer(Entity):
    customer_id: str
    email: str
    name: str
    total_orders: int = 0

@Entity.register("ORDER")
class Order(Entity):
    order_id: str
    customer_id: str
    total_amount: Decimal
    status: str
    items: list[dict[str, Any]]

@Entity.register("PRODUCT")
class Product(Entity):
    product_id: str
    name: str
    price: Decimal
    category: str
```

## Usage

```python
from datetime import datetime, timezone
from decimal import Decimal

now = datetime.now(timezone.utc)

# Create different entity types in the same table
customer = Customer(
    pk="CUSTOMER#cust-001",
    sk="PROFILE",
    customer_id="cust-001",
    email="john@example.com",
    name="John Doe",
)
customer.save()

order = Order(
    pk="CUSTOMER#cust-001",   # Same PK as customer for efficient querying
    sk="ORDER#order-001",
    order_id="order-001",
    customer_id="cust-001",
    total_amount=Decimal("199.98"),
    status="processing",
    items=[{"product_id": "prod-001", "quantity": 1}],
)
order.save()
```

## Automatic Type Resolution

Queries and scans on the base model return correctly typed instances:

```python
# Query returns mixed types — each deserialized to its registered class
items = Entity.query("CUSTOMER#cust-001").all()
for item in items:
    if isinstance(item, Customer):
        print(f"Customer: {item.name}")
    elif isinstance(item, Order):
        print(f"Order: {item.order_id} - ${item.total_amount}")

# Scan also returns correct types
all_entities = list(Entity.scan().limit(10))
products = [e for e in all_entities if isinstance(e, Product)]
```

## How It Works

1. The `Discriminator()` field stores the registered type name (e.g., `"CUSTOMER"`, `"ORDER"`)
2. On save, the discriminator value is **automatically injected** — you don't set it manually
3. On read, Dynantic uses the discriminator value to deserialize into the correct subclass

!!! tip "Access Pattern Design"
    Use the same partition key prefix for related entities (e.g., `CUSTOMER#cust-001`) to fetch them in a single query. This is the core benefit of single-table design.
