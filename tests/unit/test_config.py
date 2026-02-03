"""
Unit tests for ModelOptions configuration dataclass.

Tests the ModelOptions dataclass that stores DynamoDB model metadata.
"""

import pytest

from dynantic.config import ModelOptions


@pytest.mark.unit
class TestModelOptions:
    """Test ModelOptions dataclass."""

    def test_model_options_creation(self) -> None:
        """Test basic ModelOptions creation."""
        options = ModelOptions(
            table_name="test_table", pk_name="id", sk_name="sort_key", region="us-east-1"
        )

        assert options.table_name == "test_table"
        assert options.pk_name == "id"
        assert options.sk_name == "sort_key"
        assert options.region == "us-east-1"

    def test_model_options_defaults(self) -> None:
        """Test ModelOptions with default values."""
        options = ModelOptions(table_name="test_table", pk_name="id")

        assert options.table_name == "test_table"
        assert options.pk_name == "id"
        assert options.sk_name is None
        assert options.region == "us-east-1"  # Default region

    def test_model_options_with_sort_key(self) -> None:
        """Test ModelOptions configuration with sort key."""
        options = ModelOptions(table_name="messages", pk_name="room_id", sk_name="timestamp")

        assert options.table_name == "messages"
        assert options.pk_name == "room_id"
        assert options.sk_name == "timestamp"

    def test_model_options_without_sort_key(self) -> None:
        """Test ModelOptions configuration without sort key."""
        options = ModelOptions(table_name="users", pk_name="email")

        assert options.table_name == "users"
        assert options.pk_name == "email"
        assert options.sk_name is None

    def test_model_options_custom_region(self) -> None:
        """Test ModelOptions with custom region."""
        options = ModelOptions(table_name="test_table", pk_name="id", region="eu-south-1")

        assert options.region == "eu-south-1"

    def test_model_options_equality(self) -> None:
        """Test ModelOptions equality comparison."""
        options1 = ModelOptions(table_name="test", pk_name="id", sk_name="sk", region="us-east-1")

        options2 = ModelOptions(table_name="test", pk_name="id", sk_name="sk", region="us-east-1")

        options3 = ModelOptions(
            table_name="different", pk_name="id", sk_name="sk", region="us-east-1"
        )

        assert options1 == options2
        assert options1 != options3
