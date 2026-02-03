"""
Integration tests for CRUD operations against LocalStack.

These tests verify that the DynamoModel class works correctly with
real DynamoDB operations through LocalStack.
"""

import pytest


@pytest.mark.integration
class TestCRUDOperations:
    """Test basic CRUD operations (Create, Read, Update, Delete)."""

    def test_save_and_get_user(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test saving a user and retrieving it."""
        # Create user instance
        user = integration_user_model(**sample_user_data)

        # Save to DynamoDB
        user.save()

        # Retrieve from DynamoDB
        retrieved = integration_user_model.get(sample_user_data["email"])

        assert retrieved is not None
        assert retrieved.email == sample_user_data["email"]
        assert retrieved.username == sample_user_data["username"]
        assert retrieved.age == sample_user_data["age"]
        assert retrieved.score == sample_user_data["score"]
        assert retrieved.tags == sample_user_data["tags"]
        assert retrieved.active == sample_user_data["active"]

    def test_save_and_get_message(
        self, clean_integration_tables, integration_message_model, sample_message_data
    ):
        """Test saving a message and retrieving it."""
        # Create message instance
        message = integration_message_model(**sample_message_data)

        # Save to DynamoDB
        message.save()

        # Retrieve from DynamoDB (with both partition and sort key)
        retrieved = integration_message_model.get(
            sample_message_data["room_id"], sample_message_data["timestamp"]
        )

        assert retrieved is not None
        assert retrieved.room_id == sample_message_data["room_id"]
        assert retrieved.timestamp == sample_message_data["timestamp"]
        assert retrieved.content == sample_message_data["content"]
        assert retrieved.user == sample_message_data["user"]
        assert retrieved.likes == sample_message_data["likes"]

    def test_get_nonexistent_item_returns_none(
        self, clean_integration_tables, integration_user_model
    ):
        """Test that getting a non-existent item returns None."""
        retrieved = integration_user_model.get("nonexistent@example.com")
        assert retrieved is None

    def test_update_item(self, clean_integration_tables, integration_user_model, sample_user_data):
        """Test updating an existing item."""
        # Create and save initial user
        user = integration_user_model(**sample_user_data)
        user.save()

        # Update some fields
        user.age = 30
        user.score = 95.5
        user.tags = ["python", "testing", "updated"]
        user.save()

        # Retrieve and verify updates
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is not None
        assert retrieved.age == 30
        assert retrieved.score == 95.5
        assert retrieved.tags == ["python", "testing", "updated"]
        # Other fields should remain unchanged
        assert retrieved.username == sample_user_data["username"]
        assert retrieved.active == sample_user_data["active"]

    def test_delete_item(self, clean_integration_tables, integration_user_model, sample_user_data):
        """Test deleting an item."""
        # Create and save user
        user = integration_user_model(**sample_user_data)
        user.save()

        # Verify it exists
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is not None

        # Delete the item
        integration_user_model.delete(sample_user_data["email"])

        # Verify it's gone
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is None

    def test_delete_with_sort_key(
        self, clean_integration_tables, integration_message_model, sample_message_data
    ):
        """Test deleting an item with both partition and sort key."""
        # Create and save message
        message = integration_message_model(**sample_message_data)
        message.save()

        # Verify it exists
        retrieved = integration_message_model.get(
            sample_message_data["room_id"], sample_message_data["timestamp"]
        )
        assert retrieved is not None

        # Delete the item
        integration_message_model.delete(
            sample_message_data["room_id"], sample_message_data["timestamp"]
        )

        # Verify it's gone
        retrieved = integration_message_model.get(
            sample_message_data["room_id"], sample_message_data["timestamp"]
        )
        assert retrieved is None

    def test_delete_instance_method(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test deleting an item using the instance method."""
        # Create and save user
        user = integration_user_model(**sample_user_data)
        user.save()

        # Verify it exists
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is not None

        # Delete using instance method
        user.delete_item()

        # Verify it's gone
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is None

    def test_multiple_items_same_partition_key(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test multiple items with the same partition key but different sort keys."""
        # Save multiple messages in the same room
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":  # All test messages are in "general" room
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Retrieve each message individually
        for original_msg in messages:
            retrieved = integration_message_model.get(original_msg.room_id, original_msg.timestamp)
            assert retrieved is not None
            assert retrieved.content == original_msg.content
            assert retrieved.user == original_msg.user

    def test_save_with_special_characters(self, clean_integration_tables, integration_user_model):
        """Test saving items with special characters in attribute values."""
        special_data = {
            "email": "test+special@example.com",
            "username": "user_with_underscores",
            "age": 25,
            "score": 85.5,
            "tags": ["tag with spaces", "special-chars", "unicode: ñáéíóú"],
            "active": True,
        }

        user = integration_user_model(**special_data)
        user.save()

        retrieved = integration_user_model.get(special_data["email"])
        assert retrieved is not None
        assert retrieved.email == special_data["email"]
        assert retrieved.username == special_data["username"]
        assert retrieved.tags == special_data["tags"]


@pytest.mark.integration
class TestDataTypeHandling:
    """Test handling of different data types in DynamoDB."""

    def test_numeric_types(self, clean_integration_tables, integration_user_model):
        """Test integer and float handling."""
        user_data = {
            "email": "numeric@example.com",
            "username": "number_user",
            "age": 42,  # integer
            "score": 98.7,  # float
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert isinstance(retrieved.age, int)
        assert retrieved.age == 42
        assert isinstance(retrieved.score, float)
        assert retrieved.score == 98.7

    def test_boolean_type(self, clean_integration_tables, integration_user_model):
        """Test boolean handling."""
        # Test True
        user_data = {
            "email": "active@example.com",
            "username": "active_user",
            "age": 30,
            "active": True,
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert isinstance(retrieved.active, bool)
        assert retrieved.active is True

        # Test False
        user.active = False
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert retrieved.active is False

    def test_list_types(self, clean_integration_tables, integration_user_model):
        """Test list handling."""
        user_data = {
            "email": "list@example.com",
            "username": "list_user",
            "age": 25,
            "tags": ["python", "dynamodb", "testing", "integration"],
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert isinstance(retrieved.tags, list)
        assert retrieved.tags == ["python", "dynamodb", "testing", "integration"]

    def test_empty_lists(self, clean_integration_tables, integration_user_model):
        """Test empty list handling."""
        user_data = {
            "email": "empty@example.com",
            "username": "empty_user",
            "age": 25,
            "tags": [],  # Empty list
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert retrieved.tags == []

    def test_zero_values(self, clean_integration_tables, integration_user_model):
        """Test zero values for numeric fields."""
        user_data = {
            "email": "zero@example.com",
            "username": "zero_user",
            "age": 0,  # Zero age
            "score": 0.0,  # Zero score
        }

        user = integration_user_model(**user_data)
        user.save()

        retrieved = integration_user_model.get(user_data["email"])
        assert retrieved is not None
        assert retrieved.age == 0
        assert retrieved.score == 0.0
