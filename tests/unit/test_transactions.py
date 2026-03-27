"""Unit tests for transaction support."""

from unittest.mock import MagicMock

import pytest

from dynantic import (
    Attr,
    DynamoModel,
    Key,
    SortKey,
    TransactConditionCheck,
    TransactDelete,
    TransactGet,
    TransactPut,
    ValidationError,
)


class User(DynamoModel):
    class Meta:
        table_name = "users"

    user_id: str = Key()
    name: str
    status: str = "active"


class Order(DynamoModel):
    class Meta:
        table_name = "orders"

    order_id: str = Key()
    amount: float


@pytest.mark.unit
class TestTransactSave:
    def test_transact_save_calls_transact_write_items(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)
        mock_client.transact_write_items.return_value = {}

        user = User(user_id="u1", name="Alice")
        order = Order(order_id="o1", amount=99.99)

        DynamoModel.transact_save([user, order])

        mock_client.transact_write_items.assert_called_once()
        call_kwargs = mock_client.transact_write_items.call_args[1]
        items = call_kwargs["TransactItems"]
        assert len(items) == 2
        assert "Put" in items[0]
        assert "Put" in items[1]
        assert items[0]["Put"]["TableName"] == "users"
        assert items[1]["Put"]["TableName"] == "orders"

    def test_transact_save_rejects_over_100_items(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)

        items = [User(user_id=f"u{i}", name=f"User{i}") for i in range(101)]

        with pytest.raises(ValidationError, match="Transaction limit is 100"):
            DynamoModel.transact_save(items)


@pytest.mark.unit
class TestTransactWrite:
    def test_transact_write_mixed_actions(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)
        mock_client.transact_write_items.return_value = {}

        user = User(user_id="u1", name="Alice")

        DynamoModel.transact_write([
            TransactPut(user),
            TransactDelete(Order, order_id="o1"),
            TransactConditionCheck(User, Attr("status") == "active", user_id="u2"),
        ])

        mock_client.transact_write_items.assert_called_once()
        call_kwargs = mock_client.transact_write_items.call_args[1]
        items = call_kwargs["TransactItems"]
        assert len(items) == 3
        assert "Put" in items[0]
        assert "Delete" in items[1]
        assert "ConditionCheck" in items[2]

    def test_transact_put_with_condition(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)
        mock_client.transact_write_items.return_value = {}

        user = User(user_id="u1", name="Alice")

        DynamoModel.transact_write([
            TransactPut(user, condition=Attr("user_id").not_exists()),
        ])

        call_kwargs = mock_client.transact_write_items.call_args[1]
        put = call_kwargs["TransactItems"][0]["Put"]
        assert "ConditionExpression" in put

    def test_transact_delete_with_condition(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)
        mock_client.transact_write_items.return_value = {}

        DynamoModel.transact_write([
            TransactDelete(User, condition=Attr("status") == "inactive", user_id="u1"),
        ])

        call_kwargs = mock_client.transact_write_items.call_args[1]
        delete = call_kwargs["TransactItems"][0]["Delete"]
        assert "ConditionExpression" in delete


@pytest.mark.unit
class TestTransactGet:
    def test_transact_get_returns_models(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)

        mock_client.transact_get_items.return_value = {
            "Responses": [
                {"Item": {"user_id": {"S": "u1"}, "name": {"S": "Alice"}, "status": {"S": "active"}}},
                {"Item": {"order_id": {"S": "o1"}, "amount": {"N": "99.99"}}},
            ]
        }

        results = DynamoModel.transact_get([
            TransactGet(User, user_id="u1"),
            TransactGet(Order, order_id="o1"),
        ])

        assert len(results) == 2
        assert isinstance(results[0], User)
        assert results[0].name == "Alice"
        assert isinstance(results[1], Order)
        assert results[1].amount == 99.99

    def test_transact_get_handles_missing_items(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)

        mock_client.transact_get_items.return_value = {
            "Responses": [
                {"Item": {"user_id": {"S": "u1"}, "name": {"S": "Alice"}, "status": {"S": "active"}}},
                {},  # Missing item
            ]
        }

        results = DynamoModel.transact_get([
            TransactGet(User, user_id="u1"),
            TransactGet(Order, order_id="o999"),
        ])

        assert len(results) == 2
        assert isinstance(results[0], User)
        assert results[1] is None

    def test_transact_get_rejects_over_100_actions(self):
        mock_client = MagicMock()
        DynamoModel.set_client(mock_client)

        actions = [TransactGet(User, user_id=f"u{i}") for i in range(101)]

        with pytest.raises(ValidationError, match="Transaction limit is 100"):
            DynamoModel.transact_get(actions)
