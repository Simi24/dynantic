"""
Unit tests for auto-UUID field support.

Tests Key(auto=True), SortKey(auto=True), metaclass validation,
instantiation behavior, and the create() method.
"""

from uuid import UUID

import pytest

from dynantic import DynamoModel, Key, SortKey
from dynantic.fields import Key as KeyField
from dynantic.fields import SortKey as SortKeyField


@pytest.mark.unit
class TestAutoUUIDField:
    """Test the auto flag on Key() and SortKey() field decorators."""

    def test_key_auto_injects_flag(self) -> None:
        """Key(auto=True) injects _dynamo_auto_uuid flag."""
        field = KeyField(auto=True)
        assert field.json_schema_extra["_dynamo_auto_uuid"] is True
        assert field.json_schema_extra["_dynamo_pk"] is True

    def test_key_auto_uses_default_factory(self) -> None:
        """Key(auto=True) uses default_factory that returns UUID."""
        field = KeyField(auto=True)
        assert field.default_factory is not None
        value = field.default_factory()
        assert isinstance(value, UUID)
        assert value.version == 4

    def test_key_auto_with_default_raises(self) -> None:
        """Key(auto=True) with explicit default raises ValueError."""
        with pytest.raises(ValueError, match="Cannot use Key\\(auto=True\\)"):
            KeyField(default="explicit", auto=True)

    def test_key_no_auto_has_no_flag(self) -> None:
        """Key() without auto does not inject _dynamo_auto_uuid flag."""
        field = KeyField()
        assert "_dynamo_auto_uuid" not in field.json_schema_extra

    def test_sortkey_auto_injects_flag(self) -> None:
        """SortKey(auto=True) injects _dynamo_auto_uuid flag."""
        field = SortKeyField(auto=True)
        assert field.json_schema_extra["_dynamo_auto_uuid"] is True
        assert field.json_schema_extra["_dynamo_sk"] is True

    def test_sortkey_auto_uses_default_factory(self) -> None:
        """SortKey(auto=True) uses default_factory that returns UUID."""
        field = SortKeyField(auto=True)
        assert field.default_factory is not None
        value = field.default_factory()
        assert isinstance(value, UUID)
        assert value.version == 4

    def test_sortkey_auto_with_default_raises(self) -> None:
        """SortKey(auto=True) with explicit default raises ValueError."""
        with pytest.raises(ValueError, match="Cannot use SortKey\\(auto=True\\)"):
            SortKeyField(default="explicit", auto=True)


@pytest.mark.unit
class TestAutoUUIDMetaclass:
    """Test metaclass validation and tracking of auto-UUID fields."""

    def test_auto_uuid_tracked_in_meta(self) -> None:
        """Auto-UUID fields are tracked in _meta.auto_uuid_fields."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        assert "item_id" in Item._meta.auto_uuid_fields

    def test_has_auto_pk_true(self) -> None:
        """has_auto_pk() returns True when PK has auto=True."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        assert Item._meta.has_auto_pk() is True

    def test_has_auto_pk_false(self) -> None:
        """has_auto_pk() returns False when PK has no auto."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: str = Key()
            name: str

        assert Item._meta.has_auto_pk() is False

    def test_auto_uuid_invalid_type_raises(self) -> None:
        """Auto-UUID on non-UUID/non-str field raises ValueError."""
        with pytest.raises(ValueError, match="must be typed as UUID or str"):

            class BadItem(DynamoModel):
                class Meta:
                    table_name = "test_items"

                item_id: int = Key(auto=True)  # type: ignore[assignment]
                name: str

    def test_auto_uuid_str_type_accepted(self) -> None:
        """Auto-UUID with str type is still accepted (Pydantic coerces UUID → str)."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: str = Key(auto=True)
            name: str

        assert "item_id" in Item._meta.auto_uuid_fields

    def test_sortkey_auto_tracked(self) -> None:
        """SortKey(auto=True) is tracked in auto_uuid_fields."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            pk: str = Key()
            sk: UUID = SortKey(auto=True)
            name: str

        assert "sk" in Item._meta.auto_uuid_fields

    def test_both_pk_sk_auto(self) -> None:
        """Both PK and SK can have auto=True."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            pk: UUID = Key(auto=True)
            sk: UUID = SortKey(auto=True)
            name: str

        assert "pk" in Item._meta.auto_uuid_fields
        assert "sk" in Item._meta.auto_uuid_fields
        assert Item._meta.has_auto_pk() is True


@pytest.mark.unit
class TestAutoUUIDInstantiation:
    """Test UUID generation on model instantiation."""

    def test_generates_uuid_on_init(self) -> None:
        """Auto-UUID field generates a UUID when no value is provided."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        item = Item(name="Widget")
        assert isinstance(item.item_id, UUID)
        assert item.item_id.version == 4

    def test_unique_per_instance(self) -> None:
        """Each instance gets a unique UUID."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        item1 = Item(name="Widget")
        item2 = Item(name="Widget")
        assert item1.item_id != item2.item_id

    def test_explicit_value_overrides(self) -> None:
        """Explicit UUID value overrides auto-UUID generation."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        custom_id = UUID("12345678-1234-4234-8234-123456789abc")
        item = Item(item_id=custom_id, name="Widget")
        assert item.item_id == custom_id

    def test_explicit_string_coerced_to_uuid(self) -> None:
        """Explicit string value is coerced to UUID by Pydantic."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        item = Item(item_id="12345678-1234-4234-8234-123456789abc", name="Widget")
        assert isinstance(item.item_id, UUID)
        assert str(item.item_id) == "12345678-1234-4234-8234-123456789abc"

    def test_valid_uuid4_format(self) -> None:
        """Generated values are valid UUID4."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        for _ in range(10):
            item = Item(name="Widget")
            assert item.item_id.version == 4

    def test_composite_key_auto_sk(self) -> None:
        """SortKey(auto=True) generates UUID on init."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            pk: str = Key()
            sk: UUID = SortKey(auto=True)
            name: str

        item = Item(pk="partition", name="Widget")
        assert isinstance(item.sk, UUID)
        assert item.sk.version == 4


@pytest.mark.unit
class TestCreateMethod:
    """Test the create() classmethod with INSERT semantics."""

    def test_create_calls_save_with_not_exists(self, mock_client) -> None:
        """create() saves with Attr(pk).not_exists() condition."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        Item.set_client(mock_client)
        mock_client.put_item.return_value = {}

        Item.create(name="Widget")

        mock_client.put_item.assert_called_once()
        call_kwargs = mock_client.put_item.call_args[1]
        assert "ConditionExpression" in call_kwargs
        assert "attribute_not_exists" in call_kwargs["ConditionExpression"]

    def test_create_returns_instance(self, mock_client) -> None:
        """create() returns the created instance with UUID field."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        Item.set_client(mock_client)
        mock_client.put_item.return_value = {}

        item = Item.create(name="Widget")
        assert isinstance(item, Item)
        assert item.name == "Widget"
        assert isinstance(item.item_id, UUID)

    def test_create_with_auto_pk_generates_uuid(self, mock_client) -> None:
        """create() triggers default_factory for auto-UUID PK."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        Item.set_client(mock_client)
        mock_client.put_item.return_value = {}

        item = Item.create(name="Widget")
        assert isinstance(item.item_id, UUID)
        assert item.item_id.version == 4

    def test_create_with_explicit_pk(self, mock_client) -> None:
        """create() works with explicit PK (no auto-UUID)."""

        class User(DynamoModel):
            class Meta:
                table_name = "test_users"

            email: str = Key()
            name: str

        User.set_client(mock_client)
        mock_client.put_item.return_value = {}

        user = User.create(email="test@example.com", name="Test")
        assert user.email == "test@example.com"

    def test_create_duplicate_raises(self, mock_client) -> None:
        """create() raises ConditionalCheckFailedError on duplicate."""
        from botocore.exceptions import ClientError

        from dynantic.exceptions import ConditionalCheckFailedError

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            item_id: UUID = Key(auto=True)
            name: str

        Item.set_client(mock_client)
        mock_client.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
            "PutItem",
        )

        with pytest.raises(ConditionalCheckFailedError):
            Item.create(name="Widget")

    def test_create_composite_key(self, mock_client) -> None:
        """create() works with composite keys."""

        class Item(DynamoModel):
            class Meta:
                table_name = "test_items"

            pk: UUID = Key(auto=True)
            sk: UUID = SortKey(auto=True)
            name: str

        Item.set_client(mock_client)
        mock_client.put_item.return_value = {}

        item = Item.create(name="Widget")
        assert isinstance(item.pk, UUID)
        assert isinstance(item.sk, UUID)

        # Condition should be on PK only
        call_kwargs = mock_client.put_item.call_args[1]
        assert "attribute_not_exists" in call_kwargs["ConditionExpression"]
