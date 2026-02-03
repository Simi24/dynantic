"""
Unit tests for DynamoModel base operations with mocked boto3 client.

Tests CRUD operations, client management, and model behavior with mocked dependencies.
"""

from unittest.mock import MagicMock

import pytest

from dynantic import DynamoModel, Key


@pytest.mark.unit
class TestDynamoModelClientManagement:
    """Test client management and singleton pattern."""

    def test_get_client_singleton(self, mock_client) -> None:
        """Test that _get_client returns a singleton instance."""
        from unittest.mock import patch

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            id: str = Key()

        # Mock boto3.client to avoid region errors in CI
        with patch("boto3.client", return_value=mock_client):
            # First call should create and return the client
            client1 = TestModel._get_client()
            assert client1 is not None

            # Second call should return the same instance
            client2 = TestModel._get_client()
            assert client1 is client2

    def test_set_client_injection(self, mock_client) -> None:
        """Test that set_client allows dependency injection."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            id: str = Key()

        # Inject mock client
        TestModel.set_client(mock_client)

        # Should return the injected client
        assert TestModel._get_client() is mock_client

    def test_different_models_have_separate_clients(self, mock_client) -> None:
        """Test that different models can have different clients."""

        class ModelA(DynamoModel):
            class Meta:
                table_name = "table_a"

            id: str = Key()

        class ModelB(DynamoModel):
            class Meta:
                table_name = "table_b"

            id: str = Key()

        mock_client_a = MagicMock()
        mock_client_b = MagicMock()

        ModelA.set_client(mock_client_a)
        ModelB.set_client(mock_client_b)

        assert ModelA._get_client() is mock_client_a
        assert ModelB._get_client() is mock_client_b


@pytest.mark.unit
class TestDynamoModelGet:
    """Test the get() class method."""

    def test_get_returns_none_when_not_found(self, inject_mock_client, sample_user_model) -> None:
        """Test that get() returns None when item is not found."""
        # Mock the get_item response for not found
        inject_mock_client.get_item.return_value = {}

        result = sample_user_model.get("nonexistent@example.com")

        assert result is None
        inject_mock_client.get_item.assert_called_once()

    def test_get_returns_model_instance(self, inject_mock_client, sample_user_model) -> None:
        """Test that get() returns a model instance when found."""
        # Mock successful get_item response
        user_data = {
            "email": {"S": "test@example.com"},
            "username": {"S": "testuser"},
            "age": {"N": "25"},
            "score": {"N": "95.5"},
            "tags": {"L": [{"S": "python"}]},
            "active": {"BOOL": True},
        }
        inject_mock_client.get_item.return_value = {"Item": user_data}

        result = sample_user_model.get("test@example.com")

        assert result is not None
        assert isinstance(result, sample_user_model)
        assert result.email == "test@example.com"
        assert result.username == "testuser"
        assert result.age == 25
        assert result.score == 95.5
        assert result.tags == ["python"]
        assert result.active is True

    def test_get_with_sort_key(self, inject_mock_client, sample_message_model) -> None:
        """Test get() with both partition key and sort key."""
        message_data = {
            "room_id": {"S": "general"},
            "timestamp": {"S": "2023-01-01T10:00:00Z"},
            "content": {"S": "Hello"},
            "user": {"S": "alice"},
            "likes": {"N": "5"},
        }
        inject_mock_client.get_item.return_value = {"Item": message_data}

        result = sample_message_model.get("general", "2023-01-01T10:00:00Z")

        assert result is not None
        assert result.room_id == "general"
        assert result.timestamp == "2023-01-01T10:00:00Z"
        assert result.content == "Hello"


@pytest.mark.unit
class TestDynamoModelSave:
    """Test the save() instance method."""

    def test_save_calls_put_item(self, inject_mock_client, sample_user_model) -> None:
        """Test that save() calls put_item with correct parameters."""
        user = sample_user_model(
            email="test@example.com",
            username="testuser",
            age=25,
            score=95.5,
            tags=["python"],
            active=True,
        )

        user.save()

        # Verify put_item was called
        inject_mock_client.put_item.assert_called_once()
        call_args = inject_mock_client.put_item.call_args

        # Check table name
        assert call_args[1]["TableName"] == "test_users"

        # Check that Item contains serialized data
        item = call_args[1]["Item"]
        assert "email" in item
        assert "username" in item
        assert "age" in item
        assert "score" in item

    def test_save_serializes_data(self, inject_mock_client, sample_user_model) -> None:
        """Test that save() properly serializes all field types."""
        user = sample_user_model(
            email="test@example.com",
            username="testuser",
            age=25,
            score=95.5,
            tags=["python", "testing"],
            active=True,
        )

        user.save()

        call_args = inject_mock_client.put_item.call_args[1]
        item = call_args["Item"]

        # Check serialization of different types
        assert item["email"] == {"S": "test@example.com"}
        assert item["username"] == {"S": "testuser"}
        assert item["age"] == {"N": "25"}
        assert item["score"] == {"N": "95.5"}
        assert item["tags"] == {"L": [{"S": "python"}, {"S": "testing"}]}
        assert item["active"] == {"BOOL": True}


@pytest.mark.unit
class TestDynamoModelDelete:
    """Test delete operations."""

    def test_delete_class_method(self, inject_mock_client, sample_user_model) -> None:
        """Test class-level delete() method."""
        sample_user_model.delete("test@example.com")

        inject_mock_client.delete_item.assert_called_once()
        call_args = inject_mock_client.delete_item.call_args[1]

        assert call_args["TableName"] == "test_users"
        assert "Key" in call_args

    def test_delete_with_sort_key(self, inject_mock_client, sample_message_model) -> None:
        """Test delete with both partition and sort key."""
        sample_message_model.delete("general", "2023-01-01T10:00:00Z")

        call_args = inject_mock_client.delete_item.call_args[1]
        key = call_args["Key"]

        assert "room_id" in key
        assert "timestamp" in key

    def test_delete_item_instance_method(self, inject_mock_client, sample_user_model) -> None:
        """Test instance-level delete_item() method."""
        user = sample_user_model(email="test@example.com", username="testuser", age=25)

        user.delete_item()

        inject_mock_client.delete_item.assert_called_once()


@pytest.mark.unit
class TestDynamoModelScan:
    """Test scan operations."""

    def test_scan_returns_iterable_builder(self, inject_mock_client, sample_user_model) -> None:
        """Test that scan() returns an iterable builder."""
        # Mock scan response
        user_data = [
            {"email": {"S": "user1@example.com"}, "username": {"S": "user1"}, "age": {"N": "25"}}
        ]
        inject_mock_client.get_paginator.return_value.paginate.return_value = [{"Items": user_data}]

        result = sample_user_model.scan()

        # Should be iterable
        assert hasattr(result, "__iter__")

        # Should have builder methods
        assert hasattr(result, "filter")
        assert hasattr(result, "limit")

    def test_scan_handles_pagination(self, inject_mock_client, sample_user_model) -> None:
        """Test that scan handles multiple pages."""
        page1_data = [
            {
                "email": {"S": "user1@example.com"},
                "username": {"S": "user1"},
                "age": {"N": "25"},
                "score": {"N": "90.0"},
                "tags": {"L": []},
                "active": {"BOOL": True},
            }
        ]
        page2_data = [
            {
                "email": {"S": "user2@example.com"},
                "username": {"S": "user2"},
                "age": {"N": "30"},
                "score": {"N": "85.0"},
                "tags": {"L": []},
                "active": {"BOOL": False},
            }
        ]

        mock_paginator = inject_mock_client.get_paginator.return_value
        mock_paginator.paginate.return_value = [{"Items": page1_data}, {"Items": page2_data}]

        results = list(sample_user_model.scan())

        assert len(results) == 2
        assert results[0].email == "user1@example.com"
        assert results[0].username == "user1"
        assert results[1].email == "user2@example.com"
        assert results[1].username == "user2"


@pytest.mark.unit
class TestDynamoModelQuery:
    """Test query operations."""

    def test_query_returns_builder(self, inject_mock_client, sample_user_model) -> None:
        """Test that query() returns a DynamoQueryBuilder."""
        from dynantic.query import DynamoQueryBuilder

        builder = sample_user_model.query("test@example.com")

        assert isinstance(builder, DynamoQueryBuilder)
        assert builder.model_cls is sample_user_model
        assert builder.pk_val == "test@example.com"


@pytest.mark.unit
class TestDynamoModelValidation:
    """Test Pydantic validation behavior."""

    def test_model_forbids_extra_fields(self, sample_user_model) -> None:
        """Test that models forbid extra fields as configured."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            sample_user_model(
                email="test@example.com",
                username="testuser",
                age=25,
                extra_field="not allowed",  # Should be forbidden
            )

    def test_model_allows_defined_fields(self, sample_user_model) -> None:
        """Test that defined fields are accepted."""
        user = sample_user_model(
            email="test@example.com",
            username="testuser",
            age=25,
            score=95.5,
            tags=["python"],
            active=True,
        )

        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.age == 25
        assert user.score == 95.5
        assert user.tags == ["python"]
        assert user.active is True
