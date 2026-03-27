"""
DynamoDB Scan Operations with Builder Pattern.

This module provides the DynamoScanBuilder class for fluent, chainable
scan operations on DynamoDB tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from typing_extensions import Self

    from .model import DynamoModel
    from .pagination import PageResult

from ._logging import logger
from .builder import BaseBuilder

T = TypeVar("T", bound="DynamoModel")


class DynamoScanBuilder(BaseBuilder[T]):
    """
    Implements the Builder Pattern for DynamoDB Scans.
    Allows chaining methods (e.g., .filter().limit().using_index())
    before executing the request.
    """

    def __init__(self, model_cls: type[T], index_name: str | None = None):
        # Validate GSI before calling super (which sets up discriminator filter)
        if index_name and not model_cls._meta.has_gsi(index_name):
            raise ValueError(f"GSI '{index_name}' is not defined on model {model_cls.__name__}")

        super().__init__(model_cls, index_name)
        self._operation_name = "scan"

    # --- SCAN OPTIONS ---

    def using_index(self, index_name: str) -> Self:
        """
        Switches to scanning a different index.

        Args:
            index_name: Name of the GSI to scan

        Returns:
            Self for method chaining
        """
        if not self.config.has_gsi(index_name):
            raise ValueError(
                f"GSI '{index_name}' is not defined on model {self.model_cls.__name__}"
            )

        self.index_name = index_name
        return self

    # --- EXECUTION ---

    def _build_scan_kwargs(self) -> dict[str, Any]:
        """Builds the full kwargs dict for a DynamoDB scan."""
        kwargs = self._build_base_kwargs()

        filter_kwargs = self._build_filter_kwargs()
        if filter_kwargs:
            kwargs.update(filter_kwargs)

        return kwargs

    def __iter__(self) -> Iterator[T]:
        """
        Lazy Execution: The scan is sent to DynamoDB only when iteration starts.
        Uses a Paginator to automatically handle 'LastEvaluatedKey'.
        """
        kwargs = self._build_scan_kwargs()

        logger.info(
            "Starting scan iteration",
            extra={
                "table": self.config.table_name,
                "index": self.index_name,
                "has_filter": bool(self.filter_conditions or self.user_filter_condition),
                "limit": self.limit_val,
            },
        )

        yield from self._paginate_and_yield("scan", kwargs)

    def page(self, start_key: dict[str, Any] | None = None) -> PageResult[T]:
        """
        Executes the scan and returns a single page of results with cursor.

        Args:
            start_key: The LastEvaluated from a previous page() call.
                       Pass None for the first page.

        Returns:
            PageResult containing items and the cursor for the next page.

        Usage:
            # First page
            page1 = Movie.scan().limit(10).page()

            # Next page
            if page1.has_more:
                page2 = Movie.scan().limit(10).page(
                    start_key=page1.last_evaluated_key
                )
        """
        kwargs = self._build_scan_kwargs()

        if start_key:
            kwargs["ExclusiveStartKey"] = self.serializer.to_dynamo(start_key)

        logger.info(
            "Executing scan page",
            extra={
                "table": self.config.table_name,
                "index": self.index_name,
                "has_filter": bool(self.filter_conditions or self.user_filter_condition),
                "limit": self.limit_val,
                "has_cursor": start_key is not None,
            },
        )

        return self._execute_page("scan", kwargs)
