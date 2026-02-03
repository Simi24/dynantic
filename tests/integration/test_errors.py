"""
Integration tests for error handling and edge cases against LocalStack.

These tests verify that the library handles various error conditions and edge cases
gracefully when working with real DynamoDB through LocalStack.
"""

import pytest
from botocore.exceptions import ClientError

from dynantic.exceptions import DynanticError


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_query_nonexistent_partition_key(
        self, clean_integration_tables, integration_message_model
    ):
        """Test querying for a partition key that doesn't exist."""
        results = integration_message_model.query("nonexistent_room").all()
        assert results == []

    def test_get_nonexistent_item(self, clean_integration_tables, integration_user_model):
        """Test getting an item that doesn't exist."""
        result = integration_user_model.get("nonexistent@example.com")
        assert result is None

    def test_delete_nonexistent_item(self, clean_integration_tables, integration_user_model):
        """Test deleting an item that doesn't exist (should not raise error)."""
        # This should not raise an error - DynamoDB delete is idempotent
        integration_user_model.delete("nonexistent@example.com")

    def test_query_with_invalid_sort_key_condition(
        self, clean_integration_tables, integration_user_model, integration_message_model
    ):
        """Test query with sort key condition on table without sort key."""
        # This should raise an error since the table has no sort key
        with pytest.raises(ValueError, match="Index does not have a Sort Key defined"):
            integration_user_model.query("some_email").eq("some_value").all()

    def test_save_item_with_validation_errors(
        self, clean_integration_tables, integration_user_model
    ):
        """Test saving an item that would cause validation errors."""
        # Try to save without required fields
        with pytest.raises(ValueError):  # Pydantic validation error
            user = integration_user_model()  # Missing required email field
            user.save()

    def test_large_item_scan(self, clean_integration_tables, integration_user_model):
        """Test scanning with items that have large attribute values."""
        # Create an item with a large string
        large_data = "x" * 10000  # 10KB string
        user_data = {
            "email": "large@example.com",
            "username": f"large_user_{large_data}",
            "age": 25,
            "score": 85.0,
            "tags": ["large_data_test"],
        }

        user = integration_user_model(**user_data)
        user.save()

        # Scan should still work
        results = list(integration_user_model.scan())
        assert len(results) == 1
        assert results[0].email == user_data["email"]

    def test_special_characters_in_keys(self, clean_integration_tables, integration_user_model):
        """Test using special characters in partition keys."""
        special_emails = [
            "user+tag@example.com",
            "user.name@example.com",
            "user-name@example.com",
            "user_name@example.com",
            "user@sub.example.com",
        ]

        # Save users with special characters in email
        for email in special_emails:
            user = integration_user_model(
                email=email,
                username=f"user_{email.replace('@', '_').replace('.', '_')}",
                age=25,
                score=85.0,
            )
            user.save()

        # Retrieve each user
        for email in special_emails:
            retrieved = integration_user_model.get(email)
            assert retrieved is not None
            assert retrieved.email == email

    def test_unicode_characters(self, clean_integration_tables, integration_user_model):
        """Test handling of Unicode characters in data."""
        unicode_data = {
            "email": "unicode@example.com",
            "username": "用户",  # Chinese characters
            "age": 25,
            "score": 95.5,
            "tags": ["测试", "unicode", "ñáéíóú"],  # Mixed unicode
        }

        user = integration_user_model(**unicode_data)
        user.save()

        retrieved = integration_user_model.get(unicode_data["email"])
        assert retrieved is not None
        assert retrieved.username == unicode_data["username"]
        assert retrieved.tags == unicode_data["tags"]

    def test_empty_string_values(self, clean_integration_tables, integration_user_model):
        """Test handling of empty string values."""
        user_data = {
            "email": "empty@example.com",
            "username": "",  # Empty string
            "age": 25,
            "score": 85.0,
            "tags": [],  # Empty list
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert retrieved.username == ""
        assert retrieved.tags == []

    def test_boolean_edge_cases(self, clean_integration_tables, integration_user_model):
        """Test boolean field edge cases."""
        # Test both True and False values
        users_data = [
            {"email": "active@example.com", "username": "active", "age": 25, "active": True},
            {"email": "inactive@example.com", "username": "inactive", "age": 25, "active": False},
        ]

        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Verify both values are stored and retrieved correctly
        for user_data in users_data:
            retrieved = integration_user_model.get(user_data["email"])
            assert retrieved is not None
            assert retrieved.active == user_data["active"]
            assert isinstance(retrieved.active, bool)

    def test_numeric_precision(self, clean_integration_tables, integration_user_model):
        """Test numeric precision handling."""
        # Test various numeric values
        test_cases = [
            {"email": "int@example.com", "username": "int_user", "age": 42, "score": 100},
            {"email": "float@example.com", "username": "float_user", "age": 42, "score": 95.7},
            {"email": "negative@example.com", "username": "neg_user", "age": -5, "score": -10.5},
            {"email": "zero@example.com", "username": "zero_user", "age": 0, "score": 0.0},
        ]

        for user_data in test_cases:
            user = integration_user_model(**user_data)
            user.save()

        # Verify precision is maintained
        for user_data in test_cases:
            retrieved = integration_user_model.get(user_data["email"])
            assert retrieved is not None
            assert retrieved.age == user_data["age"]
            assert retrieved.score == user_data["score"]

    def test_query_with_empty_results(self, clean_integration_tables, integration_message_model):
        """Test query conditions that result in no matches."""
        # Save some messages
        messages_data = [
            {
                "room_id": "general",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Hello",
                "user": "alice",
                "likes": 5,
            },
            {
                "room_id": "general",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Hi there",
                "user": "bob",
                "likes": 3,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query for a timestamp that doesn't exist
        results = integration_message_model.query("general").eq("2023-01-01T12:00:00Z").all()
        assert results == []

        # Query for a room that doesn't exist
        results = integration_message_model.query("nonexistent_room").all()
        assert results == []

    def test_scan_with_no_items(self, clean_integration_tables, integration_user_model):
        """Test scanning a table with no items."""
        results = list(integration_user_model.scan())
        assert results == []

    def test_concurrent_operations(self, clean_integration_tables, integration_user_model):
        """Test multiple operations happening concurrently."""
        # This is a basic test - in a real scenario you'd use threading/multiprocessing
        # For now, just test sequential operations that could potentially conflict

        users_data = [
            {
                "email": f"concurrent{i}@example.com",
                "username": f"user{i}",
                "age": 20 + i,
                "score": 80.0 + i,
            }
            for i in range(10)
        ]

        # Save all users
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Update all users
        for user_data in users_data:
            user = integration_user_model.get(user_data["email"])
            if user:
                user.age += 1
                user.save()

        # Verify all updates worked
        for user_data in users_data:
            retrieved = integration_user_model.get(user_data["email"])
            assert retrieved is not None
            assert retrieved.age == user_data["age"] + 1  # type: ignore

    def test_large_batch_operations(self, clean_integration_tables, integration_user_model):
        """Test operations with a larger number of items."""
        # Create 100 users
        users_data = [
            {
                "email": f"batch{i:03d}@example.com",
                "username": f"user{i:03d}",
                "age": 20 + (i % 20),
                "score": 70.0 + (i % 30),
            }
            for i in range(100)
        ]

        # Save all users
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Scan all items
        results = list(integration_user_model.scan())
        assert len(results) == 100

        # Verify all items are present
        result_emails = {r.email for r in results}
        expected_emails = {u["email"] for u in users_data}
        assert result_emails == expected_emails

    def test_mixed_operations(
        self, clean_integration_tables, integration_user_model, integration_message_model
    ):
        """Test mixing different operations on different tables."""
        # Create users
        user_data = {
            "email": "mixed@example.com",
            "username": "mixed_user",
            "age": 25,
            "score": 85.0,
        }
        user = integration_user_model(**user_data)
        user.save()

        # Create messages
        message_data = {
            "room_id": "general",
            "timestamp": "2023-01-01T10:00:00Z",
            "content": "Test message",
            "user": "alice",
            "likes": 5,
        }
        message = integration_message_model(**message_data)
        message.save()

        # Verify both exist
        retrieved_user = integration_user_model.get(user_data["email"])
        retrieved_message = integration_message_model.get(
            message_data["room_id"], message_data["timestamp"]
        )

        assert retrieved_user is not None
        assert retrieved_message is not None

        # Delete user
        integration_user_model.delete(user_data["email"])

        # Verify user is gone but message remains
        assert integration_user_model.get(user_data["email"]) is None
        assert (
            integration_message_model.get(message_data["room_id"], message_data["timestamp"])
            is not None
        )


@pytest.mark.integration
class TestCustomExceptionHandling:
    """Test that custom exceptions are properly raised instead of raw ClientError."""

    @pytest.fixture
    def nonexistent_table_model(self, localstack_client):
        """Create a model pointing to a non-existent table."""
        from dynantic import DynamoModel, Key

        class NonExistentModel(DynamoModel):
            class Meta:
                table_name = "this_table_does_not_exist_12345"

            email: str = Key()
            username: str

        NonExistentModel.set_client(localstack_client)
        return NonExistentModel

    def test_no_client_error_leakage_on_get(self, nonexistent_table_model):
        """Test that get() never raises ClientError, only DynanticError subclasses."""
        # Try to get from a non-existent table
        with pytest.raises(DynanticError) as exc_info:
            nonexistent_table_model.get("test@example.com")

        # Should be our custom exception, not ClientError
        assert not isinstance(exc_info.value, ClientError)
        assert isinstance(exc_info.value, DynanticError)

    def test_no_client_error_leakage_on_save(
        self, clean_integration_tables, integration_user_model
    ):
        """Test that save() never raises ClientError, only DynanticError subclasses."""
        # Create a user with invalid data that might cause DynamoDB errors
        # This is harder to trigger in LocalStack, but we can test the wrapping
        user = integration_user_model(
            email="test@example.com",
            username="test",
            age=25,
            score=85.0,
        )

        # This should work normally, but if there were errors, they should be wrapped
        try:
            user.save()
        except Exception as e:
            # If any exception occurs, it should be our custom type
            assert not isinstance(e, ClientError)
            assert isinstance(e, DynanticError)

    def test_no_client_error_leakage_on_query(self, nonexistent_table_model):
        """Test that query() never raises ClientError, only DynanticError subclasses."""
        # Query a non-existent table should raise our custom exception
        with pytest.raises(DynanticError) as exc_info:
            list(nonexistent_table_model.query("nonexistent@example.com").all())

        assert not isinstance(exc_info.value, ClientError)
        assert isinstance(exc_info.value, DynanticError)

    def test_no_client_error_leakage_on_scan(
        self, clean_integration_tables, integration_user_model
    ):
        """Test that scan() never raises ClientError, only DynanticError subclasses."""
        # This should work normally, but if there were errors, they should be wrapped
        try:
            results = list(integration_user_model.scan())
            assert isinstance(results, list)
        except Exception as e:
            # If any exception occurs, it should be our custom type
            assert not isinstance(e, ClientError)
            assert isinstance(e, DynanticError)

    def test_no_client_error_leakage_on_delete(self, nonexistent_table_model):
        """Test that delete() never raises ClientError, only DynanticError subclasses."""
        # Delete from non-existent table should raise our custom exception
        with pytest.raises(DynanticError) as exc_info:
            nonexistent_table_model.delete("nonexistent@example.com")

        assert not isinstance(exc_info.value, ClientError)
        assert isinstance(exc_info.value, DynanticError)

    def test_exception_inheritance_preservation(self, nonexistent_table_model):
        """Test that our custom exceptions maintain proper inheritance."""
        with pytest.raises(DynanticError) as exc_info:
            nonexistent_table_model.get("test@example.com")

        error = exc_info.value
        # Should be instance of both DynanticError and Exception
        assert isinstance(error, DynanticError)
        assert isinstance(error, Exception)

        # Should have proper attributes
        assert hasattr(error, "message")
        assert hasattr(error, "original_error")

    def test_original_error_preservation(self, nonexistent_table_model):
        """Test that original ClientError is preserved in our custom exceptions."""
        with pytest.raises(DynanticError) as exc_info:
            nonexistent_table_model.get("test@example.com")

        error = exc_info.value
        # Should preserve the original error
        assert error.original_error is not None
        assert isinstance(error.original_error, ClientError)
