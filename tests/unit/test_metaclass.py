"""
Unit tests for DynamoMeta metaclass.

Tests the metaclass that processes DynamoDB model definitions and injects configuration.
"""

import pytest

from dynantic import DynamoModel, Key, SortKey
from dynantic.config import ModelOptions


@pytest.mark.unit
class TestDynamoMeta:
    """Test DynamoMeta metaclass functionality."""

    def test_metaclass_extracts_table_name(self) -> None:
        """Test that the metaclass extracts table_name from Meta class."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            id: str = Key()

        assert hasattr(TestModel, "_meta")
        assert isinstance(TestModel._meta, ModelOptions)
        assert TestModel._meta.table_name == "test_table"

    def test_metaclass_identifies_pk(self) -> None:
        """Test that the metaclass identifies the primary key field."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            user_id: str = Key()
            name: str

        assert TestModel._meta.pk_name == "user_id"

    def test_metaclass_identifies_sk(self) -> None:
        """Test that the metaclass identifies the sort key field."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            pk: str = Key()
            sk: str = SortKey()
            data: str

        assert TestModel._meta.pk_name == "pk"
        assert TestModel._meta.sk_name == "sk"

    def test_metaclass_raises_without_meta(self) -> None:
        """Test that ValueError is raised when Meta class is missing."""

        with pytest.raises(ValueError, match="missing a 'class Meta' with 'table_name'"):

            class TestModel(DynamoModel):
                id: str = Key()

    def test_metaclass_raises_without_table_name(self) -> None:
        """Test that ValueError is raised when table_name is missing from Meta."""

        with pytest.raises(ValueError, match="missing a 'table_name' in class Meta"):

            class TestModel(DynamoModel):
                class Meta:
                    pass  # No table_name

                id: str = Key()

    def test_metaclass_raises_without_pk(self) -> None:
        """Test that ValueError is raised when no Key field is defined."""

        with pytest.raises(ValueError, match="must have exactly one field defined with Key"):

            class TestModel(DynamoModel):
                class Meta:
                    table_name = "test_table"

                name: str  # No Key field

    def test_metaclass_uses_default_region(self) -> None:
        """Test that the metaclass uses the default region when not specified."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            id: str = Key()

        assert TestModel._meta.region == "us-east-1"

    def test_metaclass_custom_region(self) -> None:
        """Test that the metaclass uses custom region when specified."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"
                region = "us-west-2"

            id: str = Key()

        assert TestModel._meta.region == "us-west-2"

    def test_metaclass_skips_base_class(self) -> None:
        """Test that the metaclass skips processing the base DynamoModel class."""
        # This should not raise an error and should not set _meta
        assert not hasattr(DynamoModel, "_meta")

    def test_metaclass_model_inheritance(self) -> None:
        """Test that inherited models get their own _meta configuration."""

        class BaseModel(DynamoModel):
            class Meta:
                table_name = "base_table"

            id: str = Key()
            base_field: str

        class ChildModel(BaseModel):
            class Meta:
                table_name = "child_table"

            child_field: str

        # Both should have their own _meta
        assert BaseModel._meta.table_name == "base_table"
        assert ChildModel._meta.table_name == "child_table"
        assert BaseModel._meta.pk_name == "id"
        assert ChildModel._meta.pk_name == "id"

    def test_metaclass_model_with_multiple_inheritance(self) -> None:
        """Test metaclass behavior with multiple inheritance (should still work)."""

        class Mixin:
            mixin_field: str = "mixed"

        class TestModel(Mixin, DynamoModel):
            class Meta:
                table_name = "mixed_table"

            id: str = Key()
            data: str

        assert TestModel._meta.table_name == "mixed_table"
        assert TestModel._meta.pk_name == "id"
        assert not hasattr(TestModel._meta, "sk_name") or TestModel._meta.sk_name is None

    def test_metaclass_preserves_pydantic_config(self) -> None:
        """Test that the metaclass doesn't interfere with Pydantic model_config."""

        class TestModel(DynamoModel):
            class Meta:
                table_name = "test_table"

            id: str = Key()
            name: str

            model_config = {"extra": "forbid"}  # Should be preserved

        # Check that Pydantic config is still there
        assert hasattr(TestModel, "model_config")
        assert TestModel.model_config["extra"] == "forbid"

    def test_metaclass_handles_empty_meta_class(self) -> None:
        """Test that metaclass handles edge case of empty Meta class."""

        with pytest.raises(ValueError, match="missing a 'table_name' in class Meta"):

            class TestModel(DynamoModel):
                class Meta:
                    # Empty meta class
                    pass

                id: str = Key()
