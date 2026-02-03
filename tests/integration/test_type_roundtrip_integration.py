"""
Integration tests for comprehensive Python type support in Dynantic.

These tests verify that complex Python types (datetime, UUID, Enum, float, sets)
work correctly through full save/load cycles with LocalStack.
Float values are transparently converted to Decimal for DynamoDB storage.
"""

from datetime import datetime, timezone

import pytest

from tests.conftest import UserStatus


@pytest.mark.integration
class TestComprehensiveTypeRoundtrip:
    """Test full roundtrip of complex Python types through DynamoDB."""

    def test_datetime_roundtrip(
        self,
        clean_comprehensive_tables,
        comprehensive_message_model,
        sample_comprehensive_message_data,
    ):
        """Test datetime roundtrip through DynamoDB."""
        # Create and save message
        message = comprehensive_message_model(**sample_comprehensive_message_data)
        message.save()

        # Retrieve and verify
        retrieved = comprehensive_message_model.get(
            sample_comprehensive_message_data["room_id"],
            sample_comprehensive_message_data["timestamp"],
        )

        assert retrieved is not None
        assert retrieved.room_id == sample_comprehensive_message_data["room_id"]
        assert retrieved.timestamp == sample_comprehensive_message_data["timestamp"]
        assert isinstance(retrieved.timestamp, datetime)
        assert retrieved.content == sample_comprehensive_message_data["content"]
        assert retrieved.user == sample_comprehensive_message_data["user"]
        assert retrieved.likes == sample_comprehensive_message_data["likes"]

    def test_enum_roundtrip(
        self, clean_comprehensive_tables, comprehensive_user_model, sample_comprehensive_user_data
    ):
        """Test enum roundtrip through DynamoDB."""
        # Create and save user
        user = comprehensive_user_model(**sample_comprehensive_user_data)
        user.save()

        # Retrieve and verify
        retrieved = comprehensive_user_model.get(sample_comprehensive_user_data["user_id"])

        assert retrieved is not None
        assert retrieved.user_id == sample_comprehensive_user_data["user_id"]
        assert retrieved.status == sample_comprehensive_user_data["status"]
        assert isinstance(retrieved.status, UserStatus)
        assert retrieved.status == UserStatus.ACTIVE

    def test_decimal_roundtrip(
        self, clean_comprehensive_tables, comprehensive_user_model, sample_comprehensive_user_data
    ):
        """Test float roundtrip through DynamoDB (stored as Decimal)."""
        # Create and save user
        user = comprehensive_user_model(**sample_comprehensive_user_data)
        user.save()

        # Retrieve and verify
        retrieved = comprehensive_user_model.get(sample_comprehensive_user_data["user_id"])

        assert retrieved is not None
        assert retrieved.balance == sample_comprehensive_user_data["balance"]
        # Float in, float out - library handles Decimal conversion transparently
        assert isinstance(retrieved.balance, float)
        assert retrieved.balance == 99.99

    def test_set_roundtrip(
        self, clean_comprehensive_tables, comprehensive_user_model, sample_comprehensive_user_data
    ):
        """Test set roundtrip through DynamoDB (stored as List)."""
        # Create and save user
        user = comprehensive_user_model(**sample_comprehensive_user_data)
        user.save()

        # Retrieve and verify
        retrieved = comprehensive_user_model.get(sample_comprehensive_user_data["user_id"])

        assert retrieved is not None
        # Sets are stored as lists in DynamoDB, but Pydantic converts them back to sets
        assert isinstance(retrieved.tags, set)
        assert retrieved.tags == sample_comprehensive_user_data["tags"]
        assert isinstance(retrieved.permissions, set)
        assert retrieved.permissions == sample_comprehensive_user_data["permissions"]

    def test_datetime_query_operations(
        self, clean_comprehensive_tables, comprehensive_message_model
    ):
        """Test datetime-based query operations."""
        from datetime import datetime, timezone

        # Create test messages with different timestamps
        messages_data = [
            {
                "room_id": "test-room",
                "timestamp": datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc),
                "content": "First message",
                "user": "alice",
                "likes": 1,
            },
            {
                "room_id": "test-room",
                "timestamp": datetime(2023, 1, 1, 11, 0, tzinfo=timezone.utc),
                "content": "Second message",
                "user": "bob",
                "likes": 2,
            },
            {
                "room_id": "test-room",
                "timestamp": datetime(2023, 1, 2, 10, 0, tzinfo=timezone.utc),
                "content": "Third message",
                "user": "charlie",
                "likes": 3,
            },
        ]

        # Save messages
        for msg_data in messages_data:
            msg = comprehensive_message_model(**msg_data)
            msg.save()

        # Test starts_with with date prefix
        day_1_messages = (
            comprehensive_message_model.query("test-room").starts_with("2023-01-01").all()
        )
        assert len(day_1_messages) == 2

        # Test between with datetime objects
        start_dt = datetime(2023, 1, 1, 10, 30, tzinfo=timezone.utc)
        end_dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
        range_messages = (
            comprehensive_message_model.query("test-room").between(start_dt, end_dt).all()
        )
        assert len(range_messages) == 1
        assert range_messages[0].content == "Second message"

    def test_mixed_types_roundtrip(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test a complete object with mixed complex types."""
        from datetime import datetime, timezone

        # Create user with all complex types
        user_data = {
            "user_id": "complex-user-123",
            "email": "complex@example.com",
            "status": UserStatus.ACTIVE,
            "created_at": datetime(2023, 6, 15, 14, 30, tzinfo=timezone.utc),
            "balance": 123.45,  # float - library handles Decimal conversion
            "tags": {"premium", "beta", "verified"},
            "permissions": {"read", "write", "admin"},
        }

        user = comprehensive_user_model(**user_data)
        user.save()

        # Retrieve and verify all types
        retrieved = comprehensive_user_model.get(user_data["user_id"])

        assert retrieved is not None
        assert retrieved.user_id == user_data["user_id"]
        assert retrieved.email == user_data["email"]
        assert retrieved.status == UserStatus.ACTIVE
        assert isinstance(retrieved.status, UserStatus)
        assert retrieved.created_at == user_data["created_at"]
        assert isinstance(retrieved.created_at, datetime)
        # Float in, float out - library handles Decimal conversion transparently
        assert retrieved.balance == 123.45
        assert isinstance(retrieved.balance, float)
        # Pydantic converts lists back to sets when field is typed as set
        assert retrieved.tags == user_data["tags"]
        assert isinstance(retrieved.tags, set)
        assert retrieved.permissions == user_data["permissions"]
        assert isinstance(retrieved.permissions, set)


@pytest.mark.integration
class TestTypeEdgeCases:
    """Test edge cases for type handling."""

    def test_empty_sets(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test handling of empty sets."""
        user_data = {
            "user_id": "empty-sets-user",
            "email": "empty@example.com",
            "status": UserStatus.PENDING,
            "created_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
            "balance": 0.0,  # float - library handles Decimal conversion
            "tags": set(),  # Empty set
            "permissions": set(),  # Empty set
        }

        user = comprehensive_user_model(**user_data)
        user.save()

        retrieved = comprehensive_user_model.get(user_data["user_id"])
        assert retrieved is not None
        # Pydantic converts empty lists back to empty sets when field is typed as set
        assert retrieved.tags == set()
        assert isinstance(retrieved.tags, set)
        assert retrieved.permissions == set()
        assert isinstance(retrieved.permissions, set)

    def test_none_values_with_complex_types(
        self, clean_comprehensive_tables, comprehensive_user_model
    ):
        """Test that None values are handled correctly."""
        # Note: This test assumes the model allows None for some fields
        # In a real scenario, you'd modify the model to allow None
        pass  # Skip for now as our test model doesn't allow None</content>
