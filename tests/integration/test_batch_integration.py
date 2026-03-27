"""Integration tests for batch operations (batch_get, batch_save, batch_delete, batch_writer)."""

import pytest


@pytest.mark.integration
class TestBatchSave:
    def test_batch_save_multiple_items(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_save writes multiple items and they are retrievable."""
        users = [
            integration_user_model(email=f"user{i}@test.com", username=f"user{i}", age=20 + i)
            for i in range(5)
        ]
        integration_user_model.batch_save(users)

        for i in range(5):
            retrieved = integration_user_model.get(f"user{i}@test.com")
            assert retrieved is not None
            assert retrieved.username == f"user{i}"
            assert retrieved.age == 20 + i

    def test_batch_save_overwrites_existing(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_save overwrites items with the same key."""
        user = integration_user_model(email="dup@test.com", username="original", age=25)
        user.save()

        updated = integration_user_model(email="dup@test.com", username="updated", age=30)
        integration_user_model.batch_save([updated])

        retrieved = integration_user_model.get("dup@test.com")
        assert retrieved.username == "updated"
        assert retrieved.age == 30

    def test_batch_save_large_batch(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_save handles more than 25 items (auto-chunking)."""
        users = [
            integration_user_model(email=f"large{i}@test.com", username=f"user{i}", age=20)
            for i in range(30)
        ]
        integration_user_model.batch_save(users)

        # Verify all items exist
        all_items = list(integration_user_model.scan())
        assert len(all_items) == 30


@pytest.mark.integration
class TestBatchGet:
    def test_batch_get_multiple_items(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_get retrieves multiple items by key."""
        for i in range(5):
            integration_user_model(
                email=f"bg{i}@test.com", username=f"user{i}", age=25
            ).save()

        keys = [{"email": f"bg{i}@test.com"} for i in range(5)]
        results = integration_user_model.batch_get(keys)

        assert len(results) == 5
        emails = {r.email for r in results}
        for i in range(5):
            assert f"bg{i}@test.com" in emails

    def test_batch_get_partial_keys(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_get returns only items that exist (missing keys are skipped)."""
        integration_user_model(email="exists@test.com", username="real", age=25).save()

        keys = [{"email": "exists@test.com"}, {"email": "missing@test.com"}]
        results = integration_user_model.batch_get(keys)

        assert len(results) == 1
        assert results[0].email == "exists@test.com"

    def test_batch_get_empty_keys(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_get with empty key list returns empty list."""
        results = integration_user_model.batch_get([])
        assert results == []

    def test_batch_get_large_batch(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_get handles more than 100 keys (auto-chunking)."""
        items = [
            integration_user_model(email=f"bgl{i}@test.com", username=f"user{i}", age=20)
            for i in range(110)
        ]
        integration_user_model.batch_save(items)

        keys = [{"email": f"bgl{i}@test.com"} for i in range(110)]
        results = integration_user_model.batch_get(keys)
        assert len(results) == 110


@pytest.mark.integration
class TestBatchDelete:
    def test_batch_delete_multiple_items(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_delete removes multiple items by key."""
        for i in range(5):
            integration_user_model(
                email=f"bd{i}@test.com", username=f"user{i}", age=25
            ).save()

        keys = [{"email": f"bd{i}@test.com"} for i in range(5)]
        integration_user_model.batch_delete(keys)

        for i in range(5):
            assert integration_user_model.get(f"bd{i}@test.com") is None

    def test_batch_delete_nonexistent_keys(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_delete is idempotent for keys that don't exist."""
        keys = [{"email": "ghost@test.com"}]
        integration_user_model.batch_delete(keys)  # Should not raise

    def test_batch_delete_large_batch(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_delete handles more than 25 items (auto-chunking)."""
        items = [
            integration_user_model(email=f"bdl{i}@test.com", username=f"user{i}", age=20)
            for i in range(30)
        ]
        integration_user_model.batch_save(items)

        keys = [{"email": f"bdl{i}@test.com"} for i in range(30)]
        integration_user_model.batch_delete(keys)

        all_items = list(integration_user_model.scan())
        assert len(all_items) == 0


@pytest.mark.integration
class TestBatchWriter:
    def test_batch_writer_save(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_writer context manager saves items on exit."""
        with integration_user_model.batch_writer() as batch:
            for i in range(5):
                batch.save(
                    integration_user_model(
                        email=f"bws{i}@test.com", username=f"user{i}", age=25
                    )
                )

        for i in range(5):
            retrieved = integration_user_model.get(f"bws{i}@test.com")
            assert retrieved is not None
            assert retrieved.username == f"user{i}"

    def test_batch_writer_delete(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_writer can delete items."""
        for i in range(3):
            integration_user_model(
                email=f"bwd{i}@test.com", username=f"user{i}", age=25
            ).save()

        with integration_user_model.batch_writer() as batch:
            for i in range(3):
                batch.delete(email=f"bwd{i}@test.com")

        for i in range(3):
            assert integration_user_model.get(f"bwd{i}@test.com") is None

    def test_batch_writer_mixed_operations(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_writer handles save and delete in the same batch."""
        integration_user_model(
            email="keep@test.com", username="keep", age=25
        ).save()
        integration_user_model(
            email="remove@test.com", username="remove", age=30
        ).save()

        with integration_user_model.batch_writer() as batch:
            batch.save(
                integration_user_model(email="new@test.com", username="new", age=20)
            )
            batch.delete(email="remove@test.com")

        assert integration_user_model.get("keep@test.com") is not None
        assert integration_user_model.get("new@test.com") is not None
        assert integration_user_model.get("remove@test.com") is None

    def test_batch_writer_auto_flush(
        self, clean_integration_tables, integration_user_model
    ):
        """batch_writer auto-flushes at 25 items."""
        with integration_user_model.batch_writer() as batch:
            for i in range(30):
                batch.save(
                    integration_user_model(
                        email=f"af{i}@test.com", username=f"user{i}", age=20
                    )
                )

        all_items = list(integration_user_model.scan())
        assert len(all_items) == 30

    def test_batch_writer_with_composite_key(
        self, clean_integration_tables, integration_message_model
    ):
        """batch_writer works with composite key models."""
        with integration_message_model.batch_writer() as batch:
            for i in range(5):
                batch.save(
                    integration_message_model(
                        room_id="room1",
                        timestamp=f"2023-01-01T{10+i}:00:00Z",
                        content=f"msg{i}",
                        user="alice",
                    )
                )

        results = list(integration_message_model.query("room1"))
        assert len(results) == 5
