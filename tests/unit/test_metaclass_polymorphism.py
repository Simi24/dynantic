"""
Unit tests for metaclass discriminator discovery and entity registry.

Tests the DynamoMeta metaclass functionality for polymorphism support.
"""

import pytest

from dynantic import Discriminator, DynamoModel, Key


@pytest.mark.unit
class TestMetaclassDiscriminator:
    """Test metaclass discriminator field detection."""

    def test_detects_discriminator_field(self) -> None:
        """Metaclass should detect Discriminator() field."""

        class MyTable(DynamoModel):
            class Meta:
                table_name = "test_table"

            pk: str = Key()
            entity_type: str = Discriminator()

        assert MyTable._meta.discriminator_field == "entity_type"
        assert MyTable._meta.is_base_entity is True

    def test_no_discriminator_not_polymorphic(self) -> None:
        """Model without Discriminator should not be polymorphic."""

        class SimpleModel(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            name: str

        assert SimpleModel._meta.discriminator_field is None
        assert SimpleModel._meta.is_polymorphic() is False

    def test_raises_on_multiple_discriminators(self) -> None:
        """Should raise error if multiple discriminators defined."""
        with pytest.raises(ValueError, match="only one Discriminator"):

            class BadModel(DynamoModel):
                class Meta:
                    table_name = "test"

                pk: str = Key()
                type1: str = Discriminator()
                type2: str = Discriminator()


@pytest.mark.unit
class TestEntityRegistry:
    """Test entity registration functionality."""

    def test_register_decorator_adds_to_registry(self) -> None:
        """@register should add entity to registry."""

        class BaseTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        @BaseTable.register("USER")
        class User(BaseTable):
            name: str

        assert "USER" in BaseTable._meta.entity_registry
        assert BaseTable._meta.entity_registry["USER"] is User

    def test_register_auto_injects_discriminator_value(self) -> None:
        """@register should auto-inject discriminator value without manual field definition."""

        class BaseTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        @BaseTable.register("USER")
        class User(BaseTable):
            # No entity_type field defined - it should be auto-injected
            name: str

        # Verify the class has the discriminator value
        assert hasattr(User, "entity_type")
        assert User.entity_type == "USER"

        # Verify instances get the discriminator value automatically
        user = User(pk="123", name="Alice")
        assert user.entity_type == "USER"

        # Verify it's in model_dump
        dumped = user.model_dump()
        assert dumped["entity_type"] == "USER"

    def test_register_rejects_non_subclass(self) -> None:
        """@register should reject classes that don't inherit from base."""

        class BaseTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        class OtherModel(DynamoModel):
            class Meta:
                table_name = "other"

            pk: str = Key()
            name: str

        with pytest.raises(ValueError, match="must inherit from"):

            @BaseTable.register("OTHER")
            class Attempted(OtherModel):
                pass

    def test_register_rejects_duplicate_discriminator(self) -> None:
        """@register should reject duplicate discriminator values."""

        class BaseTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        @BaseTable.register("USER")
        class User(BaseTable):
            name: str

        with pytest.raises(ValueError, match="already registered"):

            @BaseTable.register("USER")
            class DuplicateUser(BaseTable):
                name: str

    def test_register_without_discriminator_raises(self) -> None:
        """@register on non-polymorphic model should raise."""

        class SimpleModel(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            name: str

        with pytest.raises(ValueError, match="does not have a Discriminator"):

            @SimpleModel.register("SOMETHING")
            class Bad(SimpleModel):
                pass

    def test_registered_subclass_has_correct_meta(self) -> None:
        """Registered subclass should have correct _meta attributes."""

        class BaseTable(DynamoModel):
            class Meta:
                table_name = "test"

            pk: str = Key()
            entity_type: str = Discriminator()

        @BaseTable.register("USER")
        class User(BaseTable):
            name: str

        assert User._meta.discriminator_value == "USER"
        assert User._meta.parent_model is BaseTable
        assert User._meta.is_base_entity is False
        assert User._meta.table_name == "test"  # Inherited from parent
