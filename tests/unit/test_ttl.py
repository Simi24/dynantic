"""Unit tests for TTL field support."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from dynantic import DynamoModel, Key, TTL


@pytest.mark.unit
class TestTTLFieldDetection:
    """Test that the metaclass correctly detects and validates TTL fields."""

    def test_ttl_field_detected(self):
        class Session(DynamoModel):
            class Meta:
                table_name = "sessions"

            session_id: str = Key()
            expires_at: datetime = TTL()

        assert Session._meta.ttl_field == "expires_at"

    def test_ttl_field_with_int_type(self):
        class Token(DynamoModel):
            class Meta:
                table_name = "tokens"

            token_id: str = Key()
            ttl: int = TTL()

        assert Token._meta.ttl_field == "ttl"

    def test_no_ttl_field(self):
        class User(DynamoModel):
            class Meta:
                table_name = "users"

            user_id: str = Key()
            name: str

        assert User._meta.ttl_field is None

    def test_multiple_ttl_fields_raises(self):
        with pytest.raises(ValueError, match="can have only one TTL"):

            class BadModel(DynamoModel):
                class Meta:
                    table_name = "bad"

                id: str = Key()
                expires_at: datetime = TTL()
                also_expires: datetime = TTL()

    def test_ttl_wrong_type_raises(self):
        with pytest.raises(ValueError, match="must be typed as datetime or int"):

            class BadModel(DynamoModel):
                class Meta:
                    table_name = "bad"

                id: str = Key()
                expires_at: str = TTL()


@pytest.mark.unit
class TestTTLSerialization:
    """Test TTL datetime → epoch conversion on save."""

    def test_save_converts_datetime_to_epoch(self):
        class Session(DynamoModel):
            class Meta:
                table_name = "sessions"

            session_id: str = Key()
            expires_at: datetime = TTL()

        mock_client = MagicMock()
        Session.set_client(mock_client)

        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        session = Session(session_id="s1", expires_at=ts)
        session.save()

        # Verify the put_item call
        call_kwargs = mock_client.put_item.call_args[1]
        item = call_kwargs["Item"]

        # TTL should be epoch seconds (int), not ISO string
        assert item["expires_at"] == {"N": str(int(ts.timestamp()))}

    def test_save_passes_int_ttl_through(self):
        class Token(DynamoModel):
            class Meta:
                table_name = "tokens"

            token_id: str = Key()
            ttl: int = TTL()

        mock_client = MagicMock()
        Token.set_client(mock_client)

        token = Token(token_id="t1", ttl=1735689600)
        token.save()

        call_kwargs = mock_client.put_item.call_args[1]
        item = call_kwargs["Item"]

        # int TTL should be passed through as-is
        assert item["ttl"] == {"N": "1735689600"}


@pytest.mark.unit
class TestTTLDeserialization:
    """Test TTL epoch → datetime conversion on read."""

    def test_get_converts_epoch_to_datetime(self):
        from decimal import Decimal

        class Session(DynamoModel):
            class Meta:
                table_name = "sessions"

            session_id: str = Key()
            expires_at: datetime = TTL()

        mock_client = MagicMock()
        Session.set_client(mock_client)

        epoch = 1735689600  # 2025-01-01 00:00:00 UTC
        mock_client.get_item.return_value = {
            "Item": {
                "session_id": {"S": "s1"},
                "expires_at": {"N": str(epoch)},
            }
        }

        result = Session.get("s1")
        assert result is not None
        assert isinstance(result.expires_at, datetime)
        assert result.expires_at == datetime.fromtimestamp(epoch, tz=timezone.utc)

    def test_get_int_ttl_passes_through(self):
        class Token(DynamoModel):
            class Meta:
                table_name = "tokens"

            token_id: str = Key()
            ttl: int = TTL()

        mock_client = MagicMock()
        Token.set_client(mock_client)

        mock_client.get_item.return_value = {
            "Item": {
                "token_id": {"S": "t1"},
                "ttl": {"N": "1735689600"},
            }
        }

        result = Token.get("t1")
        assert result is not None
        assert result.ttl == 1735689600
