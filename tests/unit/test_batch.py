"""Unit tests for batch operations."""

from unittest.mock import MagicMock, call

import pytest

from dynantic import DynamoModel, Key


class User(DynamoModel):
    class Meta:
        table_name = "users"

    user_id: str = Key()
    name: str


@pytest.mark.unit
class TestBatchGet:
    def test_batch_get_returns_models(self):
        mock_client = MagicMock()
        User.set_client(mock_client)

        mock_client.batch_get_item.return_value = {
            "Responses": {
                "users": [
                    {"user_id": {"S": "u1"}, "name": {"S": "Alice"}},
                    {"user_id": {"S": "u2"}, "name": {"S": "Bob"}},
                ]
            }
        }

        results = User.batch_get([{"user_id": "u1"}, {"user_id": "u2"}])

        assert len(results) == 2
        assert results[0].name in ("Alice", "Bob")
        assert results[1].name in ("Alice", "Bob")

    def test_batch_get_empty_keys(self):
        mock_client = MagicMock()
        User.set_client(mock_client)

        results = User.batch_get([])
        assert results == []

    def test_batch_get_retries_unprocessed_keys(self):
        mock_client = MagicMock()
        User.set_client(mock_client)

        # First call returns one item and one unprocessed key
        mock_client.batch_get_item.side_effect = [
            {
                "Responses": {"users": [{"user_id": {"S": "u1"}, "name": {"S": "Alice"}}]},
                "UnprocessedKeys": {
                    "users": {"Keys": [{"user_id": {"S": "u2"}}]}
                },
            },
            {
                "Responses": {"users": [{"user_id": {"S": "u2"}, "name": {"S": "Bob"}}]},
            },
        ]

        results = User.batch_get([{"user_id": "u1"}, {"user_id": "u2"}])
        assert len(results) == 2
        assert mock_client.batch_get_item.call_count == 2


@pytest.mark.unit
class TestBatchSave:
    def test_batch_save_sends_put_requests(self):
        mock_client = MagicMock()
        User.set_client(mock_client)
        mock_client.batch_write_item.return_value = {}

        users = [
            User(user_id="u1", name="Alice"),
            User(user_id="u2", name="Bob"),
        ]

        User.batch_save(users)

        mock_client.batch_write_item.assert_called_once()
        call_kwargs = mock_client.batch_write_item.call_args[1]
        requests = call_kwargs["RequestItems"]["users"]
        assert len(requests) == 2
        assert all("PutRequest" in r for r in requests)

    def test_batch_save_chunks_at_25(self):
        mock_client = MagicMock()
        User.set_client(mock_client)
        mock_client.batch_write_item.return_value = {}

        users = [User(user_id=f"u{i}", name=f"User{i}") for i in range(30)]

        User.batch_save(users)

        # Should make 2 calls: 25 + 5
        assert mock_client.batch_write_item.call_count == 2

        first_call = mock_client.batch_write_item.call_args_list[0][1]
        second_call = mock_client.batch_write_item.call_args_list[1][1]
        assert len(first_call["RequestItems"]["users"]) == 25
        assert len(second_call["RequestItems"]["users"]) == 5


@pytest.mark.unit
class TestBatchDelete:
    def test_batch_delete_sends_delete_requests(self):
        mock_client = MagicMock()
        User.set_client(mock_client)
        mock_client.batch_write_item.return_value = {}

        User.batch_delete([{"user_id": "u1"}, {"user_id": "u2"}])

        mock_client.batch_write_item.assert_called_once()
        call_kwargs = mock_client.batch_write_item.call_args[1]
        requests = call_kwargs["RequestItems"]["users"]
        assert len(requests) == 2
        assert all("DeleteRequest" in r for r in requests)


@pytest.mark.unit
class TestBatchWriter:
    def test_batch_writer_mixed_operations(self):
        mock_client = MagicMock()
        User.set_client(mock_client)
        mock_client.batch_write_item.return_value = {}

        with User.batch_writer() as batch:
            batch.save(User(user_id="u1", name="Alice"))
            batch.delete(user_id="u2")

        mock_client.batch_write_item.assert_called_once()
        call_kwargs = mock_client.batch_write_item.call_args[1]
        requests = call_kwargs["RequestItems"]["users"]
        assert len(requests) == 2
        assert "PutRequest" in requests[0]
        assert "DeleteRequest" in requests[1]

    def test_batch_writer_auto_flushes_at_25(self):
        mock_client = MagicMock()
        User.set_client(mock_client)
        mock_client.batch_write_item.return_value = {}

        with User.batch_writer() as batch:
            for i in range(30):
                batch.save(User(user_id=f"u{i}", name=f"User{i}"))

        # 25 auto-flushed + 5 flushed on exit
        assert mock_client.batch_write_item.call_count == 2
