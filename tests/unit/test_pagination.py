"""
Unit tests for pagination functionality.

Tests the PageResult dataclass and cursor serialization/deserialization.
"""

from dynantic.pagination import PageResult


class TestPageResult:
    """Test the PageResult dataclass."""

    def test_page_result_has_more_true(self):
        """Test has_more property when last_evaluated_key is present."""
        page = PageResult(
            items=[{"id": 1}, {"id": 2}], last_evaluated_key={"pk": "test", "sk": "cursor"}, count=2
        )
        assert page.has_more is True

    def test_page_result_has_more_false(self):
        """Test has_more property when last_evaluated_key is None."""
        page = PageResult(items=[{"id": 1}, {"id": 2}], last_evaluated_key=None, count=2)
        assert page.has_more is False

    def test_page_result_count_matches_items_length(self):
        """Test that count property matches the length of items."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        page = PageResult(items=items, last_evaluated_key={"pk": "test"}, count=len(items))
        assert page.count == 3
        assert len(page.items) == 3

    def test_page_result_empty_items(self):
        """Test PageResult with empty items list."""
        page = PageResult(items=[], last_evaluated_key=None, count=0)
        assert page.has_more is False
        assert page.count == 0
        assert page.items == []


class TestCursorSerialization:
    """Test cursor serialization and deserialization."""

    def test_serialize_cursor_string_key(self):
        """Test serializing a cursor with string partition key."""
        from dynantic.serializer import DynamoSerializer

        serializer = DynamoSerializer()

        # DynamoDB format (what comes from AWS)
        dynamo_key = {"email": {"S": "user@example.com"}}

        # Should convert to plain Python dict
        cursor = serializer.serialize_cursor(dynamo_key)
        assert cursor == {"email": "user@example.com"}

    def test_serialize_cursor_composite_key(self):
        """Test serializing a cursor with partition key and sort key."""
        from dynantic.serializer import DynamoSerializer

        serializer = DynamoSerializer()

        # DynamoDB format with PK and SK
        dynamo_key = {"room_id": {"S": "general"}, "timestamp": {"S": "2023-01-01T10:00:00Z"}}

        cursor = serializer.serialize_cursor(dynamo_key)
        assert cursor == {"room_id": "general", "timestamp": "2023-01-01T10:00:00Z"}

    def test_serialize_cursor_mixed_types(self):
        """Test serializing a cursor with different data types."""
        from dynantic.serializer import DynamoSerializer

        serializer = DynamoSerializer()

        dynamo_key = {"pk": {"S": "string_key"}, "sk": {"N": "123"}, "gsi_pk": {"S": "gsi_value"}}

        cursor = serializer.serialize_cursor(dynamo_key)
        assert cursor == {
            "pk": "string_key",
            "sk": 123,  # Number converted to int
            "gsi_pk": "gsi_value",
        }

    def test_deserialize_cursor_roundtrip(self):
        """Test that serialize -> deserialize is a roundtrip."""
        from dynantic.serializer import DynamoSerializer

        serializer = DynamoSerializer()

        # Start with DynamoDB format
        original_dynamo_key = {"email": {"S": "test@example.com"}, "age": {"N": "25"}}

        # Serialize to plain dict
        cursor = serializer.serialize_cursor(original_dynamo_key)

        # Deserialize back to DynamoDB format
        dynamo_key = serializer.deserialize_cursor(cursor)

        # Should match original
        assert dynamo_key == original_dynamo_key

    def test_deserialize_cursor_plain_dict(self):
        """Test deserializing a plain Python dict to DynamoDB format."""
        from dynantic.serializer import DynamoSerializer

        serializer = DynamoSerializer()

        # Plain Python dict (what frontend sends)
        cursor = {"email": "user@example.com", "score": 95.5}

        # Should convert to DynamoDB format
        dynamo_key = serializer.deserialize_cursor(cursor)
        assert dynamo_key == {
            "email": {"S": "user@example.com"},
            "score": {"N": "95.5"},  # Float becomes Decimal string
        }
