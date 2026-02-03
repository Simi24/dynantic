"""
Integration tests for scan operations against LocalStack.

These tests verify that DynamoModel.scan() works correctly with real DynamoDB
through LocalStack, including pagination and filtering.
"""

import pytest


@pytest.mark.integration
class TestScanIntegration:
    """Test scan operations with real DynamoDB operations."""

    def test_scan_empty_table(self, clean_integration_tables, integration_user_model):
        """Test scanning an empty table returns empty results."""
        results = list(integration_user_model.scan())
        assert results == []

    def test_scan_single_item(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test scanning a table with a single item."""
        # Save one user
        user = integration_user_model(**sample_user_data)
        user.save()

        # Scan the table
        results = list(integration_user_model.scan())

        assert len(results) == 1
        assert results[0].email == sample_user_data["email"]
        assert results[0].username == sample_user_data["username"]

    def test_scan_multiple_items(self, clean_integration_tables, integration_user_model):
        """Test scanning a table with multiple items."""
        # Create multiple users
        users_data = [
            {"email": "user1@example.com", "username": "user1", "age": 25, "score": 85.0},
            {"email": "user2@example.com", "username": "user2", "age": 30, "score": 92.0},
            {"email": "user3@example.com", "username": "user3", "age": 35, "score": 78.0},
        ]

        # Save all users
        saved_users = []
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()
            saved_users.append(user)

        # Scan the table
        results = list(integration_user_model.scan())

        assert len(results) == 3

        # Verify all users are returned (order may vary)
        result_emails = {r.email for r in results}
        expected_emails = {u.email for u in saved_users}
        assert result_emails == expected_emails

    def test_scan_with_limit(self, clean_integration_tables, integration_user_model):
        """Test scanning with a limit."""
        # Create multiple users
        users_data = [
            {
                "email": f"user{i}@example.com",
                "username": f"user{i}",
                "age": 20 + i,
                "score": 80.0 + i,
            }
            for i in range(5)
        ]

        # Save all users
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Scan with limit
        results = list(integration_user_model.scan().limit(3))

        # Should return at most 3 items
        assert len(results) <= 3

    def test_scan_messages_table(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test scanning the messages table."""
        # Save multiple messages
        saved_messages = []
        for msg_data in sample_messages_data:
            message = integration_message_model(**msg_data)
            message.save()
            saved_messages.append(message)

        # Scan the table
        results = list(integration_message_model.scan())

        assert len(results) == len(saved_messages)

        # Verify all messages are returned
        result_ids = {(r.room_id, r.timestamp) for r in results}
        expected_ids = {(m.room_id, m.timestamp) for m in saved_messages}
        assert result_ids == expected_ids

    def test_scan_pagination(self, clean_integration_tables, integration_user_model):
        """Test that scan handles pagination correctly."""
        # Create many users to potentially trigger pagination
        users_data = [
            {
                "email": f"user{i:03d}@example.com",
                "username": f"user{i:03d}",
                "age": 20 + (i % 20),
                "score": 70.0 + (i % 30),
            }
            for i in range(50)  # Create 50 users
        ]

        # Save all users
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Scan all items
        results = list(integration_user_model.scan())

        assert len(results) == 50

        # Verify all users are present
        result_emails = {r.email for r in results}
        expected_emails = {u["email"] for u in users_data}
        assert result_emails == expected_emails

    def test_scan_returns_iterable_builder(self, clean_integration_tables, integration_user_model):
        """Test that scan returns an iterable builder (lazy evaluation)."""
        # Save a few users
        users_data = [
            {"email": f"user{i}@example.com", "username": f"user{i}", "age": 25, "score": 85.0}
            for i in range(3)
        ]

        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Get the scan builder
        scan_builder = integration_user_model.scan()

        # Should be iterable
        assert hasattr(scan_builder, "__iter__")

        # Should have builder methods
        assert hasattr(scan_builder, "filter")
        assert hasattr(scan_builder, "limit")

        # Convert to list to consume (triggers lazy evaluation)
        results = list(scan_builder)
        assert len(results) == 3

    def test_scan_multiple_tables_isolation(
        self, clean_integration_tables, integration_user_model, integration_message_model
    ):
        """Test that scanning different tables returns different results."""
        # Save users
        user_data = {"email": "test@example.com", "username": "testuser", "age": 25, "score": 85.0}
        user = integration_user_model(**user_data)
        user.save()

        # Save messages
        message_data = {
            "room_id": "general",
            "timestamp": "2023-01-01T10:00:00Z",
            "content": "Hello",
            "user": "alice",
            "likes": 5,
        }
        message = integration_message_model(**message_data)
        message.save()

        # Scan users table
        user_results = list(integration_user_model.scan())
        assert len(user_results) == 1
        assert user_results[0].email == user_data["email"]

        # Scan messages table
        message_results = list(integration_message_model.scan())
        assert len(message_results) == 1
        assert message_results[0].room_id == message_data["room_id"]

    def test_scan_with_different_data_types(self, clean_integration_tables, integration_user_model):
        """Test scanning items with various data types."""
        # Create users with different data types
        users_data = [
            {
                "email": "string@example.com",
                "username": "string_user",
                "age": 25,  # int
                "score": 95.5,  # float
                "tags": ["tag1", "tag2"],  # list of strings
                "active": True,  # bool
            },
            {
                "email": "numbers@example.com",
                "username": "number_user",
                "age": 0,  # zero int
                "score": 0.0,  # zero float
                "tags": [],  # empty list
                "active": False,  # False bool
            },
        ]

        # Save users
        for user_data in users_data:
            user = integration_user_model(**user_data)
            user.save()

        # Scan and verify data types are preserved
        results = list(integration_user_model.scan())
        assert len(results) == 2

        # Find each user and verify their data
        for result in results:
            if result.email == "string@example.com":
                assert isinstance(result.age, int)
                assert isinstance(result.score, float)
                assert isinstance(result.tags, list)
                assert isinstance(result.active, bool)
                assert result.age == 25
                assert result.score == 95.5
                assert result.tags == ["tag1", "tag2"]
                assert result.active is True
            elif result.email == "numbers@example.com":
                assert isinstance(result.age, int)
                assert isinstance(result.score, float)
                assert isinstance(result.tags, list)
                assert isinstance(result.active, bool)
                assert result.age == 0
                assert result.score == 0.0
                assert result.tags == []
                assert result.active is False
