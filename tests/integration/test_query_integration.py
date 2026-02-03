"""
Integration tests for DynamoQueryBuilder against LocalStack.

These tests verify that query operations work correctly with real DynamoDB
through LocalStack, including various condition types and method chaining.
"""

import pytest


@pytest.mark.integration
class TestQueryBuilderIntegration:
    """Test DynamoQueryBuilder with real DynamoDB operations."""

    def test_simple_query_partition_key_only(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test querying with only partition key (should return the user)."""
        # Save a user
        user = integration_user_model(**sample_user_data)
        user.save()

        # Query for the user
        results = integration_user_model.query(sample_user_data["email"]).all()

        assert len(results) == 1
        assert results[0].email == sample_user_data["email"]
        assert results[0].username == sample_user_data["username"]

    def test_query_with_sort_key_equal(
        self, clean_integration_tables, integration_message_model, sample_message_data
    ):
        """Test querying with partition key and sort key equality."""
        # Save a message
        message = integration_message_model(**sample_message_data)
        message.save()

        # Query for the specific message
        results = (
            integration_message_model.query(sample_message_data["room_id"])
            .eq(sample_message_data["timestamp"])
            .all()
        )

        assert len(results) == 1
        assert results[0].room_id == sample_message_data["room_id"]
        assert results[0].timestamp == sample_message_data["timestamp"]
        assert results[0].content == sample_message_data["content"]

    def test_query_with_sort_key_greater_than(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying with sort key greater than condition."""
        # Save multiple messages with different timestamps
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":  # Use messages from "general" room
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Sort messages by timestamp to find the threshold
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        threshold_timestamp = sorted_messages[1].timestamp  # Second message timestamp

        # Query for messages with timestamp > threshold
        results = integration_message_model.query("general").gt(threshold_timestamp).all()

        # Should return messages after the threshold
        expected_count = len([m for m in messages if m.timestamp > threshold_timestamp])
        assert len(results) == expected_count

        # Verify all returned messages have timestamp > threshold
        for result in results:
            assert result.timestamp > threshold_timestamp

    def test_query_with_sort_key_between(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying with sort key between condition."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get timestamp range from the messages
        timestamps = sorted([m.timestamp for m in messages])
        low = timestamps[0]
        high = timestamps[-1]

        # Query for messages between first and last timestamp
        results = integration_message_model.query("general").between(low, high).all()

        # Should return all messages in the range
        assert len(results) == len(messages)

        # Verify all returned messages are within the range
        for result in results:
            assert low <= result.timestamp <= high

    def test_query_with_starts_with(self, clean_integration_tables, integration_message_model):
        """Test querying with sort key starts_with condition."""
        # Create messages with timestamps that start with different patterns
        messages_data = [
            {
                "room_id": "general",
                "timestamp": "2023-01-01T10:00:00Z",
                "content": "Morning message",
                "user": "alice",
                "likes": 5,
            },
            {
                "room_id": "general",
                "timestamp": "2023-01-01T11:00:00Z",
                "content": "Another message",
                "user": "bob",
                "likes": 3,
            },
            {
                "room_id": "general",
                "timestamp": "2023-01-02T10:00:00Z",
                "content": "Next day message",
                "user": "charlie",
                "likes": 1,
            },
            {
                "room_id": "general",
                "timestamp": "2023-02-01T10:00:00Z",
                "content": "Different month",
                "user": "diana",
                "likes": 2,
            },
        ]

        # Save messages
        for msg_data in messages_data:
            message = integration_message_model(**msg_data)
            message.save()

        # Query for messages starting with "2023-01"
        results = integration_message_model.query("general").starts_with("2023-01").all()

        # Should return 3 messages (all from January 2023)
        assert len(results) == 3

        # Verify all returned messages start with the prefix
        for result in results:
            assert result.timestamp.startswith("2023-01")

    def test_query_with_limit(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying with limit."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Query with limit of 2
        results = integration_message_model.query("general").limit(2).all()

        # Should return at most 2 results
        assert len(results) <= 2

    def test_query_reverse_order(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying with reverse order."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Query in normal order
        normal_results = integration_message_model.query("general").all()
        normal_timestamps = [r.timestamp for r in normal_results]

        # Query in reverse order
        reverse_results = integration_message_model.query("general").reverse().all()
        reverse_timestamps = [r.timestamp for r in reverse_results]

        # Should be the same items but in reverse order
        assert len(normal_results) == len(reverse_results)
        assert normal_timestamps == list(reversed(reverse_timestamps))

    def test_query_first_method(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test query first() method."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get first result
        first_result = integration_message_model.query("general").first()

        assert first_result is not None
        assert isinstance(first_result, integration_message_model)

        # Should be one of the saved messages
        saved_timestamps = {m.timestamp for m in messages}
        assert first_result.timestamp in saved_timestamps

    def test_query_one_method_single_result(
        self, clean_integration_tables, integration_message_model, sample_message_data
    ):
        """Test query one() method when exactly one result exists."""
        # Save a single message
        message = integration_message_model(**sample_message_data)
        message.save()

        # Query for exactly that message
        result = (
            integration_message_model.query(sample_message_data["room_id"])
            .eq(sample_message_data["timestamp"])
            .one()
        )

        assert result is not None
        assert isinstance(result, integration_message_model)
        assert result.room_id == sample_message_data["room_id"]
        assert result.timestamp == sample_message_data["timestamp"]
        assert result.content == sample_message_data["content"]

    def test_query_one_method_no_results(self, clean_integration_tables, integration_message_model):
        """Test query one() method when no results exist."""
        with pytest.raises(ValueError, match="No items found for this query"):
            integration_message_model.query("nonexistent_room").one()

    def test_query_method_chaining(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test complex query with multiple chained conditions."""
        # Save messages with different timestamps
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get timestamp range for complex query
        timestamps = sorted([m.timestamp for m in messages])
        mid_timestamp = timestamps[len(timestamps) // 2]

        # Complex query: partition key + sort key condition + limit + reverse
        results = (
            integration_message_model.query("general").ge(mid_timestamp).limit(2).reverse().all()
        )

        # Should return at most 2 results
        assert len(results) <= 2

        # All results should have timestamp >= mid_timestamp
        for result in results:
            assert result.timestamp >= mid_timestamp

        # Results should be in reverse order (if more than 1)
        if len(results) > 1:
            assert results[0].timestamp >= results[1].timestamp

    def test_query_different_partition_keys(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test querying different partition keys returns different results."""
        # Save messages in different rooms
        general_messages = []
        python_messages = []

        for msg_data in sample_messages_data:
            message = integration_message_model(**msg_data)
            message.save()

            if msg_data["room_id"] == "general":
                general_messages.append(message)
            elif msg_data["room_id"] == "python":
                python_messages.append(message)

        # Query general room
        general_results = integration_message_model.query("general").all()
        assert len(general_results) == len(general_messages)

        # Query python room
        python_results = integration_message_model.query("python").all()
        assert len(python_results) == len(python_messages)

        # Results should be different
        general_timestamps = {r.timestamp for r in general_results}
        python_timestamps = {r.timestamp for r in python_results}
        assert general_timestamps.isdisjoint(python_timestamps)
