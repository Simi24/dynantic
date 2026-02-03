"""
Single Table Design with Polymorphism

Demonstrates using polymorphic models for single-table design pattern.
Multiple entity types (Customer, Order, Product) share one table.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from dynantic import Discriminator, DynamoModel, Key, SortKey


class Entity(DynamoModel):
    """Base entity for single table design"""

    pk: str = Key()
    sk: str = SortKey()
    entity_type: str = Discriminator()
    created_at: datetime
    updated_at: datetime

    class Meta:
        table_name = "SingleTableExample"


@Entity.register("CUSTOMER")
class Customer(Entity):
    customer_id: str
    email: str
    name: str
    total_orders: int = 0
    lifetime_value: Decimal = Decimal("0.00")


@Entity.register("ORDER")
class Order(Entity):
    order_id: str
    customer_id: str
    total_amount: Decimal
    status: str
    items: list[dict[str, Any]]
    shipping_address: str


@Entity.register("PRODUCT")
class Product(Entity):
    product_id: str
    name: str
    price: Decimal
    stock_quantity: int
    category: str


now = datetime.now(timezone.utc)

# Create a customer
customer = Customer(
    pk="CUSTOMER#cust-001",
    sk="PROFILE",
    customer_id="cust-001",
    email="john@example.com",
    name="John Doe",
    created_at=now,
    updated_at=now,
)
customer.save()

# Create an order for the same customer (same PK for efficient querying)
order = Order(
    pk="CUSTOMER#cust-001",  # Same PK as customer
    sk="ORDER#order-001",
    order_id="order-001",
    customer_id="cust-001",
    total_amount=Decimal("199.98"),
    status="processing",
    items=[
        {"product_id": "prod-001", "quantity": 1, "price": "149.99"},
        {"product_id": "prod-002", "quantity": 1, "price": "49.99"},
    ],
    shipping_address="123 Main St",
    created_at=now,
    updated_at=now,
)
order.save()

# Create a product
product = Product(
    pk="PRODUCT#prod-001",
    sk="METADATA",
    product_id="prod-001",
    name="Wireless Headphones",
    price=Decimal("149.99"),
    stock_quantity=50,
    category="Electronics",
    created_at=now,
    updated_at=now,
)
product.save()

# Query customer and all their orders in ONE request
customer_items = Entity.query("CUSTOMER#cust-001").all()
print(f"Found {len(customer_items)} items for customer:")
for item in customer_items:
    if isinstance(item, Customer):
        print(f"  👤 Customer: {item.name}")
    elif isinstance(item, Order):
        print(f"  📦 Order: {item.order_id} - ${item.total_amount}")

# Get specific entities
customer_profile = Entity.get("CUSTOMER#cust-001", "PROFILE")
if customer_profile and isinstance(customer_profile, Customer):
    print(f"\nCustomer: {customer_profile.name} ({customer_profile.email})")

# Scan returns correctly typed instances
all_entities = list(Entity.scan().limit(10))
products = [e for e in all_entities if isinstance(e, Product)]
print(f"\nFound {len(products)} products")
