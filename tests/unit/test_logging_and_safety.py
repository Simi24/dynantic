import logging
import threading
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from dynantic.base import DynamoModel
from dynantic.fields import Key
from dynantic.updates import Add

# --- Models for Testing ---


class LogTestUser(DynamoModel):
    class Meta:
        table_name = "test_log_users"

    email: str = Key()
    age: int
    score: int = 0
    balance: float = 0.0
    my_list: list[str] = []


# --- Tests ---


def test_logging_lifecycle(mock_client, caplog):
    """Verify that logging occurs at expected levels during lifecycle ops."""
    LogTestUser.set_client(mock_client)
    # Mock return value must be in DynamoDB JSON format
    mock_client.get_item.return_value = {
        "Item": {"email": {"S": "test@example.com"}, "age": {"N": "25"}, "balance": {"N": "0"}}
    }

    caplog.set_level(logging.DEBUG, logger="dynantic")

    # 1. Test GET logging
    user = LogTestUser.get("test@example.com")

    assert "Fetching item" in caplog.text  # DEBUG
    assert "Item found" in caplog.text  # INFO

    # Check for context in logs (using redacted key)
    # We verify that 'extra' fields are present in the log records
    has_context = False
    for record in caplog.records:
        if hasattr(record, "table") and record.table == "test_log_users":
            has_context = True
            break
    assert has_context, "Log records missing 'table' context"

    # 2. Test SAVE logging
    user.save()
    assert "Saving item" in caplog.text  # INFO
    assert "Save successful" in caplog.text

    # 3. Test DELETE logging
    LogTestUser.delete("test@example.com")
    assert "Deleting item" in caplog.text
    assert "Delete successful" in caplog.text


def test_update_validation_strictness():
    """Verify strict type checking for ADD operations."""

    # 1. Valid cases
    add_int = Add("score", 10)
    add_int.validate(LogTestUser)

    add_decimal = Add("balance", Decimal("10.5"))
    add_decimal.validate(LogTestUser)

    add_set = Add("tags", {"new_tag"})
    add_set.validate(LogTestUser)  # "tags" not in model but fallback works for sets

    # 2. Invalid cases
    # Test ADD on a String field (Pydantic passes, but DynamoDB forbids ADD on String)
    with pytest.raises(ValueError, match="DynamoDB ADD supports only Numbers and Sets"):
        Add("email", "some string").validate(LogTestUser)

    # Test ADD on a List field (Pydantic passes list, but DynamoDB forbids ADD on List)
    with pytest.raises(ValueError, match="DynamoDB ADD supports only Numbers and Sets"):
        Add("my_list", ["item"]).validate(LogTestUser)


def test_contextvars_thread_safety():
    """Verify that client is isolated per-context/thread."""

    # Default global client
    global_client = MagicMock(name="global")
    LogTestUser.set_client(global_client)

    assert LogTestUser._get_client() is global_client

    # Test using_client context manager
    ctx_client = MagicMock(name="ctx")

    with LogTestUser.using_client(ctx_client):
        assert LogTestUser._get_client() is ctx_client
        assert LogTestUser._get_client() is not global_client

    # Should revert after context
    assert LogTestUser._get_client() is global_client

    # Test Thread Isolation (ContextVars are thread-local in threaded mode)
    result_holder = {}

    def thread_worker():
        thread_client = MagicMock(name="thread")
        with LogTestUser.using_client(thread_client):
            result_holder["thread_client"] = LogTestUser._get_client()
            result_holder["is_ctx"] = LogTestUser._get_client() is thread_client

    t = threading.Thread(target=thread_worker)
    t.start()
    t.join()

    assert result_holder["is_ctx"] is True
    # The main thread should still see global
    assert LogTestUser._get_client() is global_client
