"""
Unit tests for polymorphic deserialization functionality.

Tests the _deserialize_item method and related polymorphic behavior.
"""

import pytest

from dynantic import Discriminator, DynamoModel, Key


@pytest.mark.unit
class TestPolymorphicDeserialization:
    """Test polymorphic deserialization functionality."""

    @pytest.fixture
    def polymorphic_models(self, mock_client):
        """Create a polymorphic model hierarchy."""

        class MyTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        @MyTable.register("USER")
        class User(MyTable):
            name: str

        @MyTable.register("ORDER")
        class Order(MyTable):
            amount: float

        MyTable.set_client(mock_client)
        User.set_client(mock_client)
        Order.set_client(mock_client)

        return MyTable, User, Order

    def test_deserialize_to_correct_subclass(self, polymorphic_models) -> None:
        """_deserialize_item should return correct subclass based on discriminator."""
        MyTable, User, Order = polymorphic_models

        user_data = {"pk": "123", "entity_type": "USER", "name": "Alice"}
        result = MyTable._deserialize_item(user_data)

        assert isinstance(result, User)
        assert result.name == "Alice"
        assert result.entity_type == "USER"

    def test_deserialize_order_to_correct_subclass(self, polymorphic_models) -> None:
        """_deserialize_item should return Order subclass for ORDER discriminator."""
        MyTable, User, Order = polymorphic_models

        order_data = {"pk": "456", "entity_type": "ORDER", "amount": 99.99}
        result = MyTable._deserialize_item(order_data)

        assert isinstance(result, Order)
        assert result.amount == 99.99
        assert result.entity_type == "ORDER"

    def test_deserialize_unknown_discriminator_returns_base(self, polymorphic_models) -> None:
        """Unknown discriminator should fall back to base class."""
        MyTable, User, Order = polymorphic_models

        unknown_data = {"pk": "789", "entity_type": "UNKNOWN", "custom_field": "value"}
        result = MyTable._deserialize_item(unknown_data)

        assert type(result) is MyTable
        assert result.entity_type == "UNKNOWN"
        assert result.custom_field == "value"

    def test_deserialize_missing_discriminator_returns_base(self, polymorphic_models) -> None:
        """Unknown discriminator value should fall back to base class."""
        MyTable, User, Order = polymorphic_models

        unknown_discriminator_data = {"pk": "999", "entity_type": "UNKNOWN_TYPE", "name": "No Type"}
        result = MyTable._deserialize_item(unknown_discriminator_data)

        assert type(result) is MyTable
        assert result.entity_type == "UNKNOWN_TYPE"
        assert result.name == "No Type"

    def test_non_polymorphic_model_normal_deserialization(self, mock_client) -> None:
        """Non-polymorphic models should deserialize normally."""

        class SimpleModel(DynamoModel):
            class Meta:
                table_name = "simple"

            pk: str = Key()
            name: str

        SimpleModel.set_client(mock_client)

        data = {"pk": "123", "name": "Test"}
        result = SimpleModel._deserialize_item(data)

        assert isinstance(result, SimpleModel)
        assert result.name == "Test"

    def test_subclass_deserializes_as_subclass(self, polymorphic_models) -> None:
        """Subclasses should deserialize as their own type."""
        MyTable, User, Order = polymorphic_models

        # Even if we call from User class, it should still deserialize correctly
        user_data = {"pk": "123", "entity_type": "USER", "name": "Alice"}
        result = User._deserialize_item(user_data)

        assert isinstance(result, User)
        assert result.name == "Alice"
