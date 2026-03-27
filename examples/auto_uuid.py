"""
Auto-UUID Example — automatic ID generation for DynamoDB items.

Demonstrates:
- Key(auto=True) for auto-generated UUID4 partition keys
- SortKey(auto=True) for auto-generated UUID4 sort keys
- create() method with INSERT semantics (fails on duplicate)
- save() still works as upsert after create()
- Explicit PK override when needed
"""

from uuid import UUID

import boto3

from dynantic import DynamoModel, Key, SortKey

# ── Models ────────────────────────────────────────────────────────


class Product(DynamoModel):
    """Product with auto-generated UUID primary key."""

    product_id: UUID = Key(auto=True)
    name: str
    price: float
    in_stock: bool = True

    class Meta:
        table_name = "products"


class AuditLog(DynamoModel):
    """Audit log with auto-generated PK and SK (both UUID)."""

    log_id: UUID = Key(auto=True)
    entry_id: UUID = SortKey(auto=True)
    action: str
    details: str = ""

    class Meta:
        table_name = "audit_logs"


# ── Usage ─────────────────────────────────────────────────────────


def main():
    # Setup client (use LocalStack for testing)
    client = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    DynamoModel.set_client(client)

    # 1. create() — INSERT semantics with auto-UUID
    product = Product.create(name="Widget", price=29.99)
    print(f"Created product: {product.product_id}")  # UUID object
    print(f"  Type: {type(product.product_id)}")  # <class 'uuid.UUID'>
    print(f"  Name: {product.name}, Price: {product.price}")

    # 2. Retrieve by auto-generated ID
    retrieved = Product.get(product.product_id)
    print(f"\nRetrieved: {retrieved.name}")

    # 3. save() still works as upsert after create()
    product.price = 34.99
    product.save()
    print(f"\nUpdated price to: {Product.get(product.product_id).price}")

    # 4. create() with explicit UUID
    explicit_id = UUID("00000000-0000-4000-8000-000000000001")
    special = Product.create(product_id=explicit_id, name="Promo Item", price=0.0)
    print(f"\nExplicit PK: {special.product_id}")

    # 5. create() fails on duplicate (INSERT semantics)
    try:
        Product.create(product_id=explicit_id, name="Duplicate", price=0.0)
    except Exception as e:
        print(f"\nDuplicate blocked: {type(e).__name__}")

    # 6. Composite key with both auto-UUID
    log = AuditLog.create(
        action="PRODUCT_CREATED", details=f"Created {product.product_id}"
    )
    print(f"\nAudit log: pk={log.log_id}, sk={log.entry_id}")

    # 7. batch_save works with auto-UUID (UUID generated at instantiation)
    products = [Product(name=f"Item {i}", price=i * 10.0) for i in range(3)]
    Product.batch_save(products)
    print(f"\nBatch saved {len(products)} products with auto UUIDs:")
    for p in products:
        print(f"  {p.product_id}: {p.name}")


if __name__ == "__main__":
    main()
