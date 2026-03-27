"""Integration tests for auto-UUID field support against LocalStack."""

from uuid import UUID

import pytest

from dynantic import DynamoModel, Key, SortKey
from dynantic.exceptions import ConditionalCheckFailedError


@pytest.fixture
def auto_uuid_model(localstack_client):
    """Model with auto-UUID partition key."""

    class AutoItem(DynamoModel):
        class Meta:
            table_name = "integration_test_auto_uuid"

        item_id: UUID = Key(auto=True)
        name: str
        value: int = 0

    AutoItem.set_client(localstack_client)
    return AutoItem


@pytest.fixture
def auto_uuid_composite_model(localstack_client):
    """Model with auto-UUID PK and SK."""

    class AutoComposite(DynamoModel):
        class Meta:
            table_name = "integration_test_auto_uuid_composite"

        pk: UUID = Key(auto=True)
        sk: UUID = SortKey(auto=True)
        name: str

    AutoComposite.set_client(localstack_client)
    return AutoComposite


@pytest.fixture
def clean_auto_uuid_tables(localstack_helper, auto_uuid_model, auto_uuid_composite_model):
    """Creates fresh tables for auto-UUID integration tests."""
    localstack_helper.create_table(
        table_name=auto_uuid_model._meta.table_name,
        pk_name=auto_uuid_model._meta.pk_name,
        pk_type="S",
    )
    localstack_helper.create_table(
        table_name=auto_uuid_composite_model._meta.table_name,
        pk_name=auto_uuid_composite_model._meta.pk_name,
        pk_type="S",
        sk_name=auto_uuid_composite_model._meta.sk_name,
        sk_type="S",
    )

    localstack_helper.clear_table(
        table_name=auto_uuid_model._meta.table_name,
        pk_name=auto_uuid_model._meta.pk_name,
    )
    localstack_helper.clear_table(
        table_name=auto_uuid_composite_model._meta.table_name,
        pk_name=auto_uuid_composite_model._meta.pk_name,
        sk_name=auto_uuid_composite_model._meta.sk_name,
    )

    yield

    try:
        localstack_helper.clear_table(
            table_name=auto_uuid_model._meta.table_name,
            pk_name=auto_uuid_model._meta.pk_name,
        )
        localstack_helper.clear_table(
            table_name=auto_uuid_composite_model._meta.table_name,
            pk_name=auto_uuid_composite_model._meta.pk_name,
            sk_name=auto_uuid_composite_model._meta.sk_name,
        )
    except Exception:
        pass


@pytest.mark.integration
class TestAutoUUIDCreateAndGet:
    """Test create() + get() roundtrip with auto-UUID."""

    def test_create_and_get_roundtrip(self, clean_auto_uuid_tables, auto_uuid_model):
        """create() generates UUID, saves, and get() retrieves correctly."""
        item = auto_uuid_model.create(name="Widget", value=42)

        assert isinstance(item.item_id, UUID)
        assert item.item_id.version == 4

        retrieved = auto_uuid_model.get(item.item_id)
        assert retrieved is not None
        assert retrieved.item_id == item.item_id
        assert retrieved.name == "Widget"
        assert retrieved.value == 42

    def test_create_unique_ids(self, clean_auto_uuid_tables, auto_uuid_model):
        """Multiple create() calls produce unique IDs."""
        items = [auto_uuid_model.create(name=f"Item {i}") for i in range(5)]
        ids = [item.item_id for item in items]
        assert len(set(ids)) == 5

    def test_create_with_explicit_pk(self, clean_auto_uuid_tables, auto_uuid_model):
        """create() works when PK is explicitly provided."""
        explicit_id = UUID("12345678-1234-4234-8234-123456789abc")
        item = auto_uuid_model.create(item_id=explicit_id, name="Explicit")

        assert item.item_id == explicit_id
        retrieved = auto_uuid_model.get(explicit_id)
        assert retrieved is not None
        assert retrieved.name == "Explicit"

    def test_create_duplicate_raises(self, clean_auto_uuid_tables, auto_uuid_model):
        """create() with same explicit PK raises ConditionalCheckFailedError."""
        explicit_id = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
        auto_uuid_model.create(item_id=explicit_id, name="First")

        with pytest.raises(ConditionalCheckFailedError):
            auto_uuid_model.create(item_id=explicit_id, name="Second")

    def test_create_composite_key(
        self, clean_auto_uuid_tables, auto_uuid_composite_model
    ):
        """create() with composite key generates both UUIDs."""
        item = auto_uuid_composite_model.create(name="Composite")

        assert isinstance(item.pk, UUID)
        assert isinstance(item.sk, UUID)

        retrieved = auto_uuid_composite_model.get(item.pk, item.sk)
        assert retrieved is not None
        assert retrieved.name == "Composite"


@pytest.mark.integration
class TestAutoUUIDSaveAfterCreate:
    """Test that save() after create() works as upsert."""

    def test_save_updates_after_create(self, clean_auto_uuid_tables, auto_uuid_model):
        """save() after create() updates the item (upsert)."""
        item = auto_uuid_model.create(name="Original", value=1)
        item_id = item.item_id

        item.name = "Updated"
        item.value = 2
        item.save()

        retrieved = auto_uuid_model.get(item_id)
        assert retrieved.name == "Updated"
        assert retrieved.value == 2


@pytest.mark.integration
class TestAutoUUIDBatchSave:
    """Test batch_save with auto-UUID models."""

    def test_batch_save_with_auto_uuid(self, clean_auto_uuid_tables, auto_uuid_model):
        """batch_save correctly persists auto-UUID items."""
        items = [auto_uuid_model(name=f"Batch {i}", value=i) for i in range(5)]

        # Each item should have a unique auto-generated UUID
        ids = [item.item_id for item in items]
        assert len(set(ids)) == 5

        auto_uuid_model.batch_save(items)

        # Verify all items are retrievable
        for item in items:
            retrieved = auto_uuid_model.get(item.item_id)
            assert retrieved is not None
            assert retrieved.name == item.name
