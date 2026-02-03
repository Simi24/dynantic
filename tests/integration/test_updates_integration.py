import pytest

from dynantic import Add, Set
from dynantic.exceptions import ConditionalCheckFailedError


@pytest.mark.integration
class TestUpdatesIntegration:
    """Test atomic update operations against LocalStack."""

    def test_update_set_simple(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test simple SET operation."""
        # Create user
        user = comprehensive_user_model(
            user_id="u1",
            email="test@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
            tags={"A", "B"},
        )
        user.save()

        # Update status
        comprehensive_user_model.update("u1").set(
            comprehensive_user_model.status, "active"
        ).execute()

        # Verify
        updated = comprehensive_user_model.get("u1")
        assert updated.status.value == "active"  # Enum value

    def test_update_add_number(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test ADD operation on a number."""
        user = comprehensive_user_model(
            user_id="u2",
            email="u2@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
        )
        user.save()

        # Add to balance
        comprehensive_user_model.update("u2").add(comprehensive_user_model.balance, 50.0).execute()

        updated = comprehensive_user_model.get("u2")
        assert updated.balance == 150.0

    def test_update_add_set(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test ADD operation on a set."""
        user = comprehensive_user_model(
            user_id="u3",
            email="u3@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            tags={"A"},
        )
        user.save()

        # Add tag
        # Debug: check stored item
        raw = comprehensive_user_model._get_client().get_item(
            TableName=comprehensive_user_model._meta.table_name, Key={"user_id": {"S": "u3"}}
        )
        print(f"DEBUG: Stored item for u3: {raw.get('Item')}")

        comprehensive_user_model.update("u3").add(
            comprehensive_user_model.tags, {"B", "C"}
        ).execute()

        updated = comprehensive_user_model.get("u3")
        assert updated.tags == {"A", "B", "C"}

    def test_update_delete_set(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test DELETE operation on a set."""
        user = comprehensive_user_model(
            user_id="u4",
            email="u4@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            tags={"A", "B", "C"},
        )
        user.save()

        # Delete tag "B"
        comprehensive_user_model.update("u4").delete(comprehensive_user_model.tags, {"B"}).execute()

        updated = comprehensive_user_model.get("u4")
        assert updated.tags == {"A", "C"}

    def test_update_remove_attribute(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test REMOVE operation."""
        user = comprehensive_user_model(
            user_id="u5",
            email="u5@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
        )
        user.save()

        # NOTE: 'balance' is required in Pydantic model 'ComprehensiveUser' (default 0.0),
        # but in DynamoDB we can remove it.
        # Deserialization might fail if it's missing and required?
        # comprehensive_user_model defines `balance: float = 0.0`, so it has a default.
        # Pydantic will use default if missing. Good.

        comprehensive_user_model.update("u5").remove(comprehensive_user_model.balance).execute()

        # Verify raw item doesn't have balance
        # We can investigate via raw client or just check if deserialized model uses default
        # But 'balance' has default 0.0.
        updated = comprehensive_user_model.get("u5")
        assert updated.balance == 0.0

    def test_return_values_all_new(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test ReturnValues="ALL_NEW" returns the updated model."""
        user = comprehensive_user_model(
            user_id="u6",
            email="u6@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
        )
        user.save()

        result = (
            comprehensive_user_model.update("u6")
            .add(comprehensive_user_model.balance, 50.0)
            .return_values("ALL_NEW")
            .execute()
        )

        assert isinstance(result, comprehensive_user_model)
        assert result.user_id == "u6"
        assert result.balance == 150.0

    def test_conditional_update_success(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test conditional update succeeds when condition is met."""
        user = comprehensive_user_model(
            user_id="u7",
            email="u7@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
        )
        user.save()

        # Update only if status is PENDING
        comprehensive_user_model.update("u7").set(
            comprehensive_user_model.status, "active"
        ).condition(comprehensive_user_model.status == "pending").execute()

        updated = comprehensive_user_model.get("u7")
        assert updated.status.value == "active"

    def test_conditional_update_failure(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test conditional update fails when condition is not met."""
        user = comprehensive_user_model(
            user_id="u8",
            email="u8@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
        )
        user.save()

        # Update only if status is ACTIVE (which it isn't)
        with pytest.raises(ConditionalCheckFailedError):
            comprehensive_user_model.update("u8").set(
                comprehensive_user_model.balance, 200.0
            ).condition(comprehensive_user_model.status == "active").execute()

        updated = comprehensive_user_model.get("u8")
        assert updated.balance == 100.0  # Unchanged

    def test_convenience_update_item(self, clean_comprehensive_tables, comprehensive_user_model):
        """Test usage of update_item convenience method."""
        user = comprehensive_user_model(
            user_id="u9",
            email="u9@example.com",
            status="pending",
            created_at="2023-01-01T00:00:00Z",
            balance=100.0,
            tags={"A"},
        )
        user.save()

        updated = comprehensive_user_model.update_item(
            key={"user_id": "u9"},
            actions=[
                Set(comprehensive_user_model.status, "active"),
                Add(comprehensive_user_model.balance, 20.0),
                Add(comprehensive_user_model.tags, {"B"}),
            ],
            return_values="ALL_NEW",
        )

        assert updated.status.value == "active"
        assert updated.balance == 120.0
        assert updated.tags == {"A", "B"}
