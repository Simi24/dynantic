"""
Integration tests for conditional writes against LocalStack.

These tests verify that conditional operations (save/delete) work correctly
with real DynamoDB (LocalStack).
"""

import pytest

from dynantic import ConditionalCheckFailedError


@pytest.mark.integration
class TestConditionalWrites:
    """Test conditional save and delete operations."""

    def test_create_if_not_exists(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test creating an item only if it does not exist."""
        # 1. First save should succeed
        user = integration_user_model(**sample_user_data)
        # Use DSL: integration_user_model.email.not_exists()
        user.save(condition=integration_user_model.email.not_exists())

        # Verify it exists
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is not None
        assert retrieved.email == sample_user_data["email"]

        # 2. Second save with same condition should fail
        with pytest.raises(ConditionalCheckFailedError):
            user.save(condition=integration_user_model.email.not_exists())

    def test_optimistic_locking(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test updating an item only if a condition matches (simulating optimistic locking)."""
        # Create initial user with age 25
        user = integration_user_model(**sample_user_data)
        user.age = 25
        user.save()

        # Update should fail if we expect age to be 30
        user.age = 26
        with pytest.raises(ConditionalCheckFailedError):
            user.save(condition=integration_user_model.age == 30)

        # Update should succeed if we expect age to be 25
        user.save(condition=integration_user_model.age == 25)

        # Verify update happened
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved.age == 26

    def test_conditional_delete(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test deleting an item only if a condition matches."""
        # Create user
        user = integration_user_model(**sample_user_data)
        user.active = True
        user.save()

        # Delete should fail if we require active=False
        with pytest.raises(ConditionalCheckFailedError):
            user.delete_item(condition=integration_user_model.active == False)

        # Verify user still exists
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is not None

        # Delete should succeed if we require active=True
        user.delete_item(condition=integration_user_model.active == True)

        # Verify user is gone
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved is None

    def test_complex_conditions(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test complex conditions with AND/OR/NOT."""
        user = integration_user_model(**sample_user_data)
        user.age = 30
        user.active = True
        user.score = 50.0
        user.save()

        # Update should fail if (age < 20) OR (active == False)
        user.score = 100.0
        # Use DSL with model fields
        condition = (integration_user_model.age < 20) | (integration_user_model.active == False)

        with pytest.raises(ConditionalCheckFailedError):
            user.save(condition=condition)

        # Verify no change
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved.score == 50.0

        # Update should succeed if (age > 20) AND (active == True)
        condition = (integration_user_model.age > 20) & (integration_user_model.active == True)
        user.save(condition=condition)

        # Verify change
        retrieved = integration_user_model.get(sample_user_data["email"])
        assert retrieved.score == 100.0

    def test_class_method_conditional_delete(
        self, clean_integration_tables, integration_user_model, sample_user_data
    ):
        """Test conditional delete using the class method."""
        user = integration_user_model(**sample_user_data)
        user.score = 100.0
        user.save()

        # Should fail if score < 50
        with pytest.raises(ConditionalCheckFailedError):
            integration_user_model.delete(
                sample_user_data["email"], condition=integration_user_model.score < 50
            )

        # Should succeed if score == 100
        integration_user_model.delete(
            sample_user_data["email"], condition=integration_user_model.score == 100
        )

        assert integration_user_model.get(sample_user_data["email"]) is None
