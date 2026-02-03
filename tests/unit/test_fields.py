"""
Unit tests for field decorators (Key, SortKey).

Tests the field marker functions that inject DynamoDB key metadata.
"""

import pytest
from pydantic import Field

from dynantic.fields import Discriminator, GSIKey, GSISortKey, Key, SortKey


@pytest.mark.unit
class TestKeyField:
    """Test the Key() field decorator."""

    def test_key_marks_pk_flag(self) -> None:
        """Test that Key() injects the _dynamo_pk flag."""
        field = Key()
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_pk"] is True

    def test_key_with_default_value(self) -> None:
        """Test Key with a default value."""
        field = Key(default="test@example.com")
        assert field.default == "test@example.com"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_pk"] is True

    def test_key_with_field_kwargs(self) -> None:
        """Test Key with additional Field kwargs."""
        field = Key(description="User email", min_length=5)
        assert field.description == "User email"
        # Check that validation constraints are stored
        assert hasattr(field, "metadata")
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_pk"] is True

    def test_key_preserves_existing_schema_extra(self) -> None:
        """Test that Key merges with existing json_schema_extra."""
        existing_extra = {"custom_field": "value"}
        field = Key(json_schema_extra=existing_extra)
        expected_extra = {"custom_field": "value", "_dynamo_pk": True}
        assert field.json_schema_extra == expected_extra

    def test_key_returns_field_instance(self) -> None:
        """Test that Key returns a Pydantic Field instance."""
        field = Key()
        assert isinstance(field, type(Field()))

    def test_key_with_none_default(self) -> None:
        """Test Key with None as default."""
        field = Key(default=None)
        assert field.default is None
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_pk"] is True


@pytest.mark.unit
class TestSortKeyField:
    """Test the SortKey() field decorator."""

    def test_sortkey_marks_sk_flag(self) -> None:
        """Test that SortKey() injects the _dynamo_sk flag."""
        field = SortKey()
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_sk"] is True

    def test_sortkey_with_default_value(self) -> None:
        """Test SortKey with a default value."""
        field = SortKey(default="2023-01-01")
        assert field.default == "2023-01-01"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_sk"] is True

    def test_sortkey_with_field_kwargs(self) -> None:
        """Test SortKey with additional Field kwargs."""
        field = SortKey(description="Timestamp", pattern=r"\d{4}-\d{2}-\d{2}")
        assert field.description == "Timestamp"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_sk"] is True

    def test_sortkey_preserves_existing_schema_extra(self) -> None:
        """Test that SortKey merges with existing json_schema_extra."""
        existing_extra = {"validation": "timestamp"}
        field = SortKey(json_schema_extra=existing_extra)
        expected_extra = {"validation": "timestamp", "_dynamo_sk": True}
        assert field.json_schema_extra == expected_extra

    def test_sortkey_returns_field_instance(self) -> None:
        """Test that SortKey returns a Pydantic Field instance."""
        field = SortKey()
        assert isinstance(field, type(Field()))

    def test_sortkey_with_none_default(self) -> None:
        """Test SortKey with None as default."""
        field = SortKey(default=None)
        assert field.default is None
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_sk"] is True


@pytest.mark.unit
class TestKeySortKeySeparation:
    """Test that Key and SortKey flags are separate."""

    def test_key_does_not_have_sk_flag(self) -> None:
        """Test that Key() does not inject _dynamo_sk flag."""
        field = Key()
        assert "_dynamo_sk" not in field.json_schema_extra

    def test_sortkey_does_not_have_pk_flag(self) -> None:
        """Test that SortKey() does not inject _dynamo_pk flag."""
        field = SortKey()
        assert "_dynamo_pk" not in field.json_schema_extra

    def test_both_flags_can_be_present(self) -> None:
        """Test that both flags can coexist (though not recommended)."""
        # This is technically possible but not the intended use
        field = Field(json_schema_extra={"_dynamo_pk": True, "_dynamo_sk": True})
        assert field.json_schema_extra["_dynamo_pk"] is True
        assert field.json_schema_extra["_dynamo_sk"] is True


@pytest.mark.unit
class TestGSIKeyField:
    """Test the GSIKey() field decorator."""

    def test_gsikey_marks_gsi_pk_flag(self) -> None:
        """Test that GSIKey() injects the _dynamo_gsi_pk flag."""
        field = GSIKey(index_name="test-index")
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_pk"] == "test-index"

    def test_gsikey_with_default_value(self) -> None:
        """Test GSIKey with a default value."""
        field = GSIKey(index_name="test-index", default="default-val")
        assert field.default == "default-val"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_pk"] == "test-index"

    def test_gsikey_with_field_kwargs(self) -> None:
        """Test GSIKey with additional Field kwargs."""
        field = GSIKey(index_name="test-index", description="Customer ID", min_length=5)
        assert field.description == "Customer ID"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_pk"] == "test-index"

    def test_gsikey_preserves_existing_schema_extra(self) -> None:
        """Test that GSIKey merges with existing json_schema_extra."""
        existing_extra = {"custom_field": "value"}
        field = GSIKey(index_name="test-index", json_schema_extra=existing_extra)
        expected_extra = {"custom_field": "value", "_dynamo_gsi_pk": "test-index"}
        assert field.json_schema_extra == expected_extra

    def test_gsikey_returns_field_instance(self) -> None:
        """Test that GSIKey returns a Pydantic Field instance."""
        field = GSIKey(index_name="test-index")
        assert isinstance(field, type(Field()))

    def test_gsikey_with_none_default(self) -> None:
        """Test GSIKey with None as default."""
        field = GSIKey(index_name="test-index", default=None)
        assert field.default is None
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_pk"] == "test-index"


@pytest.mark.unit
class TestGSISortKeyField:
    """Test the GSISortKey() field decorator."""

    def test_gsisortkey_marks_gsi_sk_flag(self) -> None:
        """Test that GSISortKey() injects the _dynamo_gsi_sk flag."""
        field = GSISortKey(index_name="test-index")
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_sk"] == "test-index"

    def test_gsisortkey_with_default_value(self) -> None:
        """Test GSISortKey with a default value."""
        field = GSISortKey(index_name="test-index", default="2023-01-01")
        assert field.default == "2023-01-01"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_sk"] == "test-index"

    def test_gsisortkey_with_field_kwargs(self) -> None:
        """Test GSISortKey with additional Field kwargs."""
        field = GSISortKey(
            index_name="test-index", description="Order date", pattern=r"\d{4}-\d{2}-\d{2}"
        )
        assert field.description == "Order date"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_sk"] == "test-index"

    def test_gsisortkey_preserves_existing_schema_extra(self) -> None:
        """Test that GSISortKey merges with existing json_schema_extra."""
        existing_extra = {"validation": "timestamp"}
        field = GSISortKey(index_name="test-index", json_schema_extra=existing_extra)
        expected_extra = {"validation": "timestamp", "_dynamo_gsi_sk": "test-index"}
        assert field.json_schema_extra == expected_extra

    def test_gsisortkey_returns_field_instance(self) -> None:
        """Test that GSISortKey returns a Pydantic Field instance."""
        field = GSISortKey(index_name="test-index")
        assert isinstance(field, type(Field()))

    def test_gsisortkey_with_none_default(self) -> None:
        """Test GSISortKey with None as default."""
        field = GSISortKey(index_name="test-index", default=None)
        assert field.default is None
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_gsi_sk"] == "test-index"


@pytest.mark.unit
class TestGSIKeyGSISortKeySeparation:
    """Test that GSIKey and GSISortKey flags are separate."""

    def test_gsikey_does_not_have_gsi_sk_flag(self) -> None:
        """Test that GSIKey() does not inject _dynamo_gsi_sk flag."""
        field = GSIKey(index_name="test-index")
        assert "_dynamo_gsi_sk" not in field.json_schema_extra

    def test_gsisortkey_does_not_have_gsi_pk_flag(self) -> None:
        """Test that GSISortKey() does not inject _dynamo_gsi_pk flag."""
        field = GSISortKey(index_name="test-index")
        assert "_dynamo_gsi_pk" not in field.json_schema_extra

    def test_both_gsi_flags_can_be_present(self) -> None:
        """Test that both GSI flags can coexist (though not recommended)."""
        # This is technically possible but not the intended use
        field = Field(json_schema_extra={"_dynamo_gsi_pk": "idx1", "_dynamo_gsi_sk": "idx2"})
        assert field.json_schema_extra["_dynamo_gsi_pk"] == "idx1"
        assert field.json_schema_extra["_dynamo_gsi_sk"] == "idx2"


@pytest.mark.unit
class TestDiscriminatorField:
    """Test the Discriminator() field decorator."""

    def test_discriminator_marks_flag(self) -> None:
        """Test that Discriminator() injects the _dynamo_discriminator flag."""
        field = Discriminator()
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_discriminator"] is True

    def test_discriminator_with_default_value(self) -> None:
        """Test Discriminator with a default value."""
        field = Discriminator(default="USER")
        assert field.default == "USER"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_discriminator"] is True

    def test_discriminator_with_field_kwargs(self) -> None:
        """Test Discriminator with additional Field kwargs."""
        field = Discriminator(description="Entity type", min_length=3)
        assert field.description == "Entity type"
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_discriminator"] is True

    def test_discriminator_preserves_existing_schema_extra(self) -> None:
        """Test that Discriminator merges with existing json_schema_extra."""
        existing_extra = {"custom_field": "value"}
        field = Discriminator(json_schema_extra=existing_extra)
        expected_extra = {"custom_field": "value", "_dynamo_discriminator": True}
        assert field.json_schema_extra == expected_extra

    def test_discriminator_returns_field_instance(self) -> None:
        """Test that Discriminator returns a Pydantic Field instance."""
        field = Discriminator()
        assert isinstance(field, type(Field()))

    def test_discriminator_with_none_default(self) -> None:
        """Test Discriminator with None as default."""
        field = Discriminator(default=None)
        assert field.default is None
        assert field.json_schema_extra is not None
        assert field.json_schema_extra["_dynamo_discriminator"] is True
