"""
DynamoDB client management for Dynantic.

Provides global client singleton and thread-safe/async-safe
client overrides via contextvars.
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import boto3

_global_client: Any | None = None
_client_context: ContextVar[Any | None] = ContextVar("dynamo_client", default=None)


def get_client() -> Any:
    """
    Returns a Boto3 DynamoDB Client.
    Uses a singleton pattern to avoid multiple instantiations.

    Priority:
        1. ContextVar override (thread-safe/async-safe, set via using_client)
        2. Global default (set via set_client)
        3. Auto-created default client
    """
    # 1. Check ContextVar (Thread-safe/Async-safe override)
    ctx_client = _client_context.get()
    if ctx_client is not None:
        return ctx_client

    # 2. Check Global Default
    global _global_client
    if _global_client is not None:
        return _global_client

    # 3. Initialize Default Global Client
    _global_client = boto3.client("dynamodb")
    return _global_client


def set_client(client: Any) -> None:
    """
    Sets the global default DynamoDB client.
    Useful for testing or advanced configurations.
    """
    global _global_client
    _global_client = client


@contextmanager
def using_client(client: Any) -> Generator[None, None, None]:
    """
    Context manager to scope a client to a block of code.
    Thread-safe and Async-safe using contextvars.

    Usage:
        with using_client(my_client):
            User.get("...")
    """
    token = _client_context.set(client)
    try:
        yield
    finally:
        _client_context.reset(token)
