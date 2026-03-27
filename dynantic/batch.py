"""
Batch operations for Dynantic.

Provides batch_get, batch_write (put + delete), and a BatchWriter
context manager with auto-flush at the DynamoDB 25-item limit.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ._logging import logger
from .exceptions import handle_dynamo_errors

if TYPE_CHECKING:
    from .model import DynamoModel
    from .serializer import DynamoSerializer

BATCH_WRITE_LIMIT = 25
BATCH_GET_LIMIT = 100
MAX_RETRIES = 5
BASE_BACKOFF = 0.05  # 50ms


class BatchWriter:
    """
    Context manager for mixed batch put/delete operations with auto-flush.

    Usage:
        with User.batch_writer() as batch:
            batch.save(user1)
            batch.save(user2)
            batch.delete(user_id="u3")
    """

    def __init__(
        self,
        model_cls: type[DynamoModel],
        client: Any,
        serializer: DynamoSerializer,
        table_name: str,
    ) -> None:
        self._model_cls = model_cls
        self._client = client
        self._serializer = serializer
        self._table_name = table_name
        self._buffer: list[dict[str, Any]] = []

    def save(self, item: DynamoModel) -> None:
        """Add a PutItem request to the batch."""
        data = item.model_dump(mode="python", exclude_none=True)

        # Handle TTL conversion
        config = item._meta
        if config.ttl_field and config.ttl_field in data:
            ttl_value = data[config.ttl_field]
            if isinstance(ttl_value, datetime):
                data[config.ttl_field] = int(ttl_value.timestamp())

        dynamo_item = self._serializer.to_dynamo(data)
        self._buffer.append({"PutRequest": {"Item": dynamo_item}})

        if len(self._buffer) >= BATCH_WRITE_LIMIT:
            self._flush()

    def delete(self, **key_values: Any) -> None:
        """Add a DeleteItem request to the batch."""
        dynamo_key = self._serializer.to_dynamo(key_values)
        self._buffer.append({"DeleteRequest": {"Key": dynamo_key}})

        if len(self._buffer) >= BATCH_WRITE_LIMIT:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return

        with handle_dynamo_errors(table_name=self._table_name):
            batch_write_with_retry(self._client, self._table_name, list(self._buffer))
        self._buffer.clear()

    def __enter__(self) -> BatchWriter:
        return self

    def __exit__(self, *args: Any) -> None:
        self._flush()


# ── Internal helpers ───────────────────────────────────────────────


def batch_write_with_retry(client: Any, table_name: str, requests: list[dict[str, Any]]) -> None:
    """Execute batch_write_item with chunking and exponential backoff."""
    for i in range(0, len(requests), BATCH_WRITE_LIMIT):
        chunk = requests[i : i + BATCH_WRITE_LIMIT]
        _execute_batch_write_chunk(client, table_name, chunk)


def _execute_batch_write_chunk(client: Any, table_name: str, chunk: list[dict[str, Any]]) -> None:
    """Execute a single chunk with retry for unprocessed items."""
    unprocessed = chunk
    for attempt in range(MAX_RETRIES):
        response = client.batch_write_item(RequestItems={table_name: unprocessed})
        unprocessed_items = response.get("UnprocessedItems", {}).get(table_name, [])
        if not unprocessed_items:
            return
        unprocessed = unprocessed_items

        logger.debug(
            "Retrying unprocessed batch write items",
            extra={
                "table": table_name,
                "unprocessed_count": len(unprocessed),
                "attempt": attempt + 1,
            },
        )
        time.sleep(BASE_BACKOFF * (2**attempt))

    raise RuntimeError(
        f"Failed to write {len(unprocessed)} items to '{table_name}' after {MAX_RETRIES} retries"
    )


def batch_get_with_retry(
    client: Any, table_name: str, keys: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Execute batch_get_item with chunking and exponential backoff."""
    all_items: list[dict[str, Any]] = []

    for i in range(0, len(keys), BATCH_GET_LIMIT):
        chunk = keys[i : i + BATCH_GET_LIMIT]
        items = _execute_batch_get_chunk(client, table_name, chunk)
        all_items.extend(items)

    return all_items


def _execute_batch_get_chunk(
    client: Any, table_name: str, chunk: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Execute a single chunk of batch_get_item with retry."""
    all_items: list[dict[str, Any]] = []
    unprocessed_keys = chunk

    for attempt in range(MAX_RETRIES):
        response = client.batch_get_item(RequestItems={table_name: {"Keys": unprocessed_keys}})
        items = response.get("Responses", {}).get(table_name, [])
        all_items.extend(items)

        unprocessed = response.get("UnprocessedKeys", {}).get(table_name, {})
        unprocessed_keys = unprocessed.get("Keys", [])
        if not unprocessed_keys:
            return all_items

        logger.debug(
            "Retrying unprocessed batch get keys",
            extra={
                "table": table_name,
                "unprocessed_count": len(unprocessed_keys),
                "attempt": attempt + 1,
            },
        )
        time.sleep(BASE_BACKOFF * (2**attempt))

    # Return what we got even if some keys are still unprocessed
    return all_items
