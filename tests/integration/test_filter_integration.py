"""
Integration tests for filter support on queries and scans against LocalStack.

These tests verify that filtering on non-primary key fields works correctly
with real DynamoDB through Local Stack.
"""

import pytest


@pytest.mark.integration
class TestQueryFilterIntegration:
    """Test query filter operations with real DynamoDB."""

    def test_query_with_simple_filter(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying with simple filter on non-key field."""
        # Save multiple messages
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()

        # Query with filter on likes
        results = (
            integration_message_model.query("general")
            .filter(integration_message_model.likes >= 3)
            .all()
        )

        # Verify all returned messages have likes >= 3
        assert len(results) > 0
        for result in results:
            assert result.likes >= 3

    def test_query_with_multiple_filters_and(
        self, clean_integration_tables, integration_message_model
    ):
        """Test querying with multiple filters combined with AND."""
        # Create test messages
        messages_data = [
            {
                "room_id": "test",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Low likes",
                "user": "alice",
                "likes": 2,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "High likes bob",
                "user": "bob",
                "likes": 10,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "High likes charlie",
                "user": "charlie",
                "likes": 8,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T13:00:00Z",
                "content": "Medium likes",
                "user": "alice",
                "likes": 5,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query with multiple filters (likes >= 5 AND user == "charlie")
        results = (
            integration_message_model.query("test")
            .filter(integration_message_model.likes >= 5)
            .filter(integration_message_model.user == "charlie")
            .all()
        )

        # Should return only charlie's message with likes >= 5
        assert len(results) == 1
        assert results[0].user == "charlie"
        assert results[0].likes >= 5

    def test_query_with_complex_filter_or(
        self, clean_integration_tables, integration_message_model
    ):
        """Test querying with complex filter using OR."""
        # Create test messages
        messages_data = [
            {
                "room_id": "test",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Low likes alice",
                "user": "alice",
                "likes": 2,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "High likes bob",
                "user": "bob",
                "likes": 10,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Low likes charlie",
                "user": "charlie",
                "likes": 1,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T13:00:00Z",
                "content": "High likes alice",
                "user": "alice",
                "likes": 8,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query with OR condition: likes >= 8 OR user == "charlie"

        condition = (integration_message_model.likes >= 8) | (
            integration_message_model.user == "charlie"
        )
        results = integration_message_model.query("test").filter(condition).all()

        # Should return messages matching either condition
        assert len(results) == 3  # bob (10 likes), charlie (1 like), alice (8 likes)

        for result in results:
            # Each result should match at least one condition
            assert result.likes >= 8 or result.user == "charlie"

    def test_query_filter_with_key_condition(
        self, clean_integration_tables, integration_message_model
    ):
        """Test filter combined with key condition."""
        # Create messages with different timestamps
        messages_data = [
            {
                "room_id": "test",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Morning",
                "user": "alice",
                "likes": 5,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Midday",
                "user": "bob",
                "likes": 3,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-02T10:00:00Z",
                "content": "Next day",
                "user": "charlie",
                "likes": 10,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query with key condition (starts_with) AND filter (likes >= 5)
        results = (
            integration_message_model.query("test")
            .starts_with("2023-01-01")
            .filter(integration_message_model.likes >= 5)
            .all()
        )

        # Should return only messages from 2023-01-01 with likes >= 5
        assert len(results) == 1
        assert results[0].timestamp.startswith("2023-01-01")
        assert results[0].likes >= 5

    def test_query_filter_contains(self, clean_integration_tables, integration_message_model):
        """Test query filter with contains operator on string."""
        # Create test messages
        messages_data = [
            {
                "room_id": "test",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Hello world",
                "user": "alice",
                "likes": 5,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Goodbye everyone",
                "user": "bob",
                "likes": 3,
            },
            {
                "room_id": "test",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Hello there",
                "user": "charlie",
                "likes": 2,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query with filter using contains on content
        from dynantic import Attr

        results = (
            integration_message_model.query("test").filter(Attr("content").contains("Hello")).all()
        )

        # Should return messages containing "Hello"
        assert len(results) == 2
        for result in results:
            assert "Hello" in result.content


@pytest.mark.integration
class TestScanFilterIntegration:
    """Test scan filter operations with real DynamoDB."""

    def test_scan_with_simple_filter(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test scanning with simple filter on non-key field."""
        # Save messages from different rooms
        for msg_data in sample_messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with filter on likes
        results = (
            integration_message_model.scan().filter(integration_message_model.likes >= 5).all()
        )

        # Verify all returned messages have likes >= 5
        assert len(results) > 0
        for result in results:
            assert result.likes >= 5

    def test_scan_with_multiple_filters(self, clean_integration_tables, integration_message_model):
        """Test scanning with multiple filters combined with AND."""
        # Create test messages
        messages_data = [
            {
                "room_id": "room1",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Test",
                "user": "alice",
                "likes": 2,
            },
            {
                "room_id": "room2",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Test",
                "user": "bob",
                "likes": 10,
            },
            {
                "room_id": "room3",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Test",
                "user": "charlie",
                "likes": 8,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with multiple filters
        results = (
            integration_message_model.scan()
            .filter(integration_message_model.likes >= 8)
            .filter(integration_message_model.user == "bob")
            .all()
        )

        # Should return only bob's message with likes >= 8
        assert len(results) == 1
        assert results[0].user == "bob"
        assert results[0].likes >= 8

    def test_scan_with_complex_filter_or(self, clean_integration_tables, integration_message_model):
        """Test scanning with complex filter using OR."""
        # Create test messages
        messages_data = [
            {
                "room_id": "room1",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Test",
                "user": "alice",
                "likes": 2,
            },
            {
                "room_id": "room2",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Test",
                "user": "bob",
                "likes": 10,
            },
            {
                "room_id": "room3",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Test",
                "user": "charlie",
                "likes": 1,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with OR condition
        condition = (integration_message_model.likes >= 10) | (
            integration_message_model.user == "charlie"
        )
        results = integration_message_model.scan().filter(condition).all()

        # Should return messages matching either condition
        assert len(results) == 2  # bob and charlie

        for result in results:
            assert result.likes >= 10 or result.user == "charlie"

    def test_scan_with_limit(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test scan with filter and limit."""
        # Save multiple messages
        for msg_data in sample_messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with filter and limit
        results = (
            integration_message_model.scan()
            .filter(integration_message_model.likes >= 1)
            .limit(3)
            .all()
        )

        # Should return at most 3 results
        assert len(results) <= 3
        for result in results:
            assert result.likes >= 1

    def test_scan_between_operator(self, clean_integration_tables, integration_message_model):
        """Test scan with between operator."""
        # Create test messages with varying likes
        messages_data = [
            {
                "room_id": "room1",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Test",
                "user": "alice",
                "likes": 1,
            },
            {
                "room_id": "room2",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Test",
                "user": "bob",
                "likes": 5,
            },
            {
                "room_id": "room3",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Test",
                "user": "charlie",
                "likes": 8,
            },
            {
                "room_id": "room4",
                "timestamp": "2023-01-01T13:00:00Z",
                "content": "Test",
                "user": "diana",
                "likes": 10,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with between filter
        from dynantic import Attr

        results = integration_message_model.scan().filter(Attr("likes").between(5, 8)).all()

        # Should return messages with likes between 5 and 8 (inclusive)
        assert len(results) == 2  # bob (5) and charlie (8)
        for result in results:
            assert 5 <= result.likes <= 8

    def test_scan_begins_with(self, clean_integration_tables, integration_message_model):
        """Test scan with begins_with operator."""
        # Create test messages
        messages_data = [
            {
                "room_id": "room1",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Test",
                "user": "alice_admin",
                "likes": 5,
            },
            {
                "room_id": "room2",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Test",
                "user": "alice_user",
                "likes": 3,
            },
            {
                "room_id": "room3",
                "timestamp": "2023-01-01T12:00:00Z",
                "content": "Test",
                "user": "bob_user",
                "likes": 2,
            },
        ]

        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Scan with begins_with filter
        from dynantic import Attr

        results = integration_message_model.scan().filter(Attr("user").begins_with("alice")).all()

        # Should return messages from users starting with "alice"
        assert len(results) == 2
        for result in results:
            assert result.user.startswith("alice")


# Note: Polymorphism filter test removed - pending proper fixture setup
