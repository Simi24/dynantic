"""
Pagination support for Dynantic.

This module provides data structures and utilities for external pagination control,
enabling FastAPI backends to return pagination cursors to frontends.
"""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class PageResult(Generic[T]):
    """
    Represents a single page of results with pagination cursor.

    Attributes:
        items: List of model instances for this page
        last_evaluated_key: Cursor for the next page (None if no more pages)
        count: Number of items in this page
    """

    items: list[T]
    last_evaluated_key: dict[str, Any] | None
    count: int

    @property
    def has_more(self) -> bool:
        """Returns True if there are more pages available."""
        return self.last_evaluated_key is not None
