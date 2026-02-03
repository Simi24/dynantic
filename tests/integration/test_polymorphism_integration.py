"""
Integration tests for polymorphism/single-table design functionality.

Tests polymorphic queries and scans against LocalStack.
"""

from collections.abc import Generator
from typing import Any

import pytest

from dynantic import Discriminator, DynamoModel, Key, SortKey


@pytest.mark.integration
class TestPolymorphismIntegration:
    """Integration tests for polymorphic single-table design."""

    @pytest.fixture
    def polymorphic_table(
        self, localstack_client: Any, localstack_helper: Any
    ) -> Generator[tuple[type[DynamoModel], type[DynamoModel], type[DynamoModel]], None, None]:
        """Create polymorphic models and table."""

        class MyTable(DynamoModel):
            class Meta:
                table_name = "polymorphic_test"

            pk: str = Key()
            sk: str = SortKey()  # Sort key for more complex scenarios
            entity_type: str = Discriminator()
            created_at: str = ""

        @MyTable.register("USER")
        class User(MyTable):
            name: str
            email: str

        @MyTable.register("ORDER")
        class Order(MyTable):
            amount: float
            items: list[str] = []

        # Set client
        MyTable.set_client(localstack_client)
        User.set_client(localstack_client)
        Order.set_client(localstack_client)

        # Create table
        localstack_helper.create_table(table_name="polymorphic_test", pk_name="pk", sk_name="sk")

        yield MyTable, User, Order

        # Cleanup
        localstack_helper.clear_table("polymorphic_test", "pk", "sk")

    def test_save_and_query_mixed_entities(self, polymorphic_table) -> None:
        """Query from base class should return mixed entity types."""
        MyTable, User, Order = polymorphic_table

        # Save user
        user = User(
            pk="CUST#123",
            sk="PROFILE",
            created_at="2023-01-01",
            name="Alice",
            email="alice@example.com",
        )
        user.save()

        # Save order
        order = Order(
            pk="CUST#123",
            sk="ORDER#001",
            created_at="2023-01-02",
            amount=99.99,
            items=["laptop"],
        )
        order.save()

        # Query from base class
        results = MyTable.query("CUST#123").all()

        assert len(results) == 2
        types = {type(r) for r in results}
        assert User in types
        assert Order in types

    def test_subclass_query_filters_by_discriminator(self, polymorphic_table) -> None:
        """Query from subclass should only return that entity type."""
        MyTable, User, Order = polymorphic_table

        # Save multiple entities
        User(pk="CUST#123", sk="PROFILE", name="Alice", email="a@b.com", created_at="").save()
        Order(pk="CUST#123", sk="ORDER#001", amount=50.0, created_at="").save()
        Order(pk="CUST#123", sk="ORDER#002", amount=75.0, created_at="").save()

        # Query users only
        users = User.query("CUST#123").all()
        assert len(users) == 1
        assert all(isinstance(u, User) for u in users)

        # Query orders only
        orders = Order.query("CUST#123").all()
        assert len(orders) == 2
        assert all(isinstance(o, Order) for o in orders)

    def test_scan_from_base_returns_all_types(self, polymorphic_table) -> None:
        """Scan from base class returns all entity types."""
        MyTable, User, Order = polymorphic_table

        User(pk="U1", sk="P", name="Alice", email="a@b.com", created_at="").save()
        User(pk="U2", sk="P", name="Bob", email="b@b.com", created_at="").save()
        Order(pk="O1", sk="D", amount=100.0, created_at="").save()

        results = list(MyTable.scan())

        assert len(results) == 3
        user_count = sum(1 for r in results if isinstance(r, User))
        order_count = sum(1 for r in results if isinstance(r, Order))
        assert user_count == 2
        assert order_count == 1

    def test_scan_from_subclass_filters(self, polymorphic_table) -> None:
        """Scan from subclass only returns that type."""
        MyTable, User, Order = polymorphic_table

        User(pk="U1", sk="P", name="Alice", email="a@b.com", created_at="").save()
        Order(pk="O1", sk="D", amount=100.0, created_at="").save()

        users = list(User.scan())

        assert len(users) == 1
        assert isinstance(users[0], User)

    def test_get_from_base_returns_correct_type(self, polymorphic_table) -> None:
        """Get from base class returns correct entity type."""
        MyTable, User, Order = polymorphic_table

        User(pk="U1", sk="P", name="Alice", email="a@b.com", created_at="").save()
        Order(pk="O1", sk="D", amount=100.0, created_at="").save()

        # Get user
        user = MyTable.get("U1", "P")
        assert isinstance(user, User)
        assert user.name == "Alice"

        # Get order
        order = MyTable.get("O1", "D")
        assert isinstance(order, Order)
        assert order.amount == 100.0

    def test_get_from_subclass_works_normally(self, polymorphic_table) -> None:
        """Get from subclass works normally."""
        MyTable, User, Order = polymorphic_table

        User(pk="U1", sk="P", name="Alice", email="a@b.com", created_at="").save()

        user = User.get("U1", "P")
        assert isinstance(user, User)
        assert user.name == "Alice"
