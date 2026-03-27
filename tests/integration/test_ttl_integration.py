"""Integration tests for TTL (Time To Live) field support."""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.integration
class TestTTLDatetime:
    """Tests for TTL fields typed as datetime."""

    def test_save_and_get_roundtrip(
        self, clean_ttl_tables, integration_ttl_model, localstack_client
    ):
        """datetime TTL is stored as epoch seconds and deserialized back to datetime."""
        expires = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        session = integration_ttl_model(
            session_id="s1", user_id="u1", expires_at=expires
        )
        session.save()

        # Verify raw DynamoDB stores epoch int (N type)
        raw = localstack_client.get_item(
            TableName="integration_test_sessions",
            Key={"session_id": {"S": "s1"}},
        )
        assert "N" in raw["Item"]["expires_at"]
        assert int(raw["Item"]["expires_at"]["N"]) == int(expires.timestamp())

        # Verify model deserializes back to datetime
        retrieved = integration_ttl_model.get("s1")
        assert isinstance(retrieved.expires_at, datetime)
        assert retrieved.expires_at == expires

    def test_ttl_preserves_timezone(self, clean_ttl_tables, integration_ttl_model):
        """TTL roundtrip preserves UTC timezone info."""
        expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        session = integration_ttl_model(
            session_id="s2", user_id="u1", expires_at=expires
        )
        session.save()

        retrieved = integration_ttl_model.get("s2")
        assert retrieved.expires_at.tzinfo is not None
        assert int(retrieved.expires_at.timestamp()) == int(expires.timestamp())

    def test_ttl_future_and_past(self, clean_ttl_tables, integration_ttl_model):
        """Both future and past TTL values are stored correctly."""
        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)

        integration_ttl_model(
            session_id="future", user_id="u1", expires_at=future
        ).save()
        integration_ttl_model(
            session_id="past", user_id="u1", expires_at=past
        ).save()

        assert integration_ttl_model.get("future").expires_at == future
        assert integration_ttl_model.get("past").expires_at == past


@pytest.mark.integration
class TestTTLInt:
    """Tests for TTL fields typed as int (raw epoch seconds)."""

    def test_int_ttl_roundtrip(
        self, clean_ttl_tables, integration_ttl_int_model, localstack_client
    ):
        """int TTL is stored and retrieved as-is (no conversion)."""
        epoch = 1750000000
        token = integration_ttl_int_model(token_id="t1", ttl=epoch)
        token.save()

        # Raw DynamoDB should have N type
        raw = localstack_client.get_item(
            TableName="integration_test_tokens",
            Key={"token_id": {"S": "t1"}},
        )
        assert int(raw["Item"]["ttl"]["N"]) == epoch

        retrieved = integration_ttl_int_model.get("t1")
        assert retrieved.ttl == epoch

    def test_int_ttl_zero(self, clean_ttl_tables, integration_ttl_int_model):
        """Zero epoch is a valid TTL value."""
        token = integration_ttl_int_model(token_id="t-zero", ttl=0)
        token.save()
        assert integration_ttl_int_model.get("t-zero").ttl == 0


@pytest.mark.integration
class TestTTLWithBatchAndTransactions:
    """TTL works correctly through batch and transaction paths."""

    def test_batch_save_preserves_ttl(
        self, clean_ttl_tables, integration_ttl_model, localstack_client
    ):
        """batch_save correctly converts datetime TTL to epoch."""
        expires = datetime(2027, 3, 15, tzinfo=timezone.utc)
        items = [
            integration_ttl_model(
                session_id=f"bs{i}", user_id="u1", expires_at=expires
            )
            for i in range(3)
        ]
        integration_ttl_model.batch_save(items)

        for i in range(3):
            retrieved = integration_ttl_model.get(f"bs{i}")
            assert isinstance(retrieved.expires_at, datetime)
            assert retrieved.expires_at == expires

    def test_batch_writer_preserves_ttl(
        self, clean_ttl_tables, integration_ttl_model
    ):
        """batch_writer context manager correctly converts datetime TTL."""
        expires = datetime(2027, 6, 1, tzinfo=timezone.utc)
        with integration_ttl_model.batch_writer() as batch:
            for i in range(3):
                batch.save(
                    integration_ttl_model(
                        session_id=f"bw{i}", user_id="u1", expires_at=expires
                    )
                )

        for i in range(3):
            retrieved = integration_ttl_model.get(f"bw{i}")
            assert retrieved.expires_at == expires

    def test_transact_save_preserves_ttl(
        self, clean_ttl_tables, integration_ttl_model
    ):
        """transact_save correctly converts datetime TTL to epoch."""
        from dynantic import DynamoModel

        expires = datetime(2028, 1, 1, tzinfo=timezone.utc)
        items = [
            integration_ttl_model(
                session_id=f"ts{i}", user_id="u1", expires_at=expires
            )
            for i in range(3)
        ]
        DynamoModel.transact_save(items)

        for i in range(3):
            retrieved = integration_ttl_model.get(f"ts{i}")
            assert isinstance(retrieved.expires_at, datetime)
            assert retrieved.expires_at == expires
