"""
DynamoDB Scan Operations with Builder Pattern.

This module provides the DynamoScanBuilder class for fluent, chainable
scan operations on DynamoDB tables.
"""

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .conditions import Condition
    from .pagination import PageResult

if TYPE_CHECKING:
    # Prevent circular imports at runtime
    from .base import DynamoModel

from ._logging import logger
from .exceptions import handle_dynamo_errors

# Generic TypeVar for model typing, bound to DynamoModel
T = TypeVar("T", bound="DynamoModel")


class DynamoScanBuilder(Iterable[T]):
    """
    Implements the Builder Pattern for DynamoDB Scans.
    Allows chaining methods (e.g., .filter().limit().using_index())
    before executing the request.
    """

    def __init__(self, model_cls: type[T], index_name: str | None = None):
        self.model_cls = model_cls
        self.config = model_cls._meta
        self.client = model_cls._get_client()
        self.serializer = model_cls._serializer

        # Validate GSI if specified
        if index_name and not self.config.has_gsi(index_name):
            raise ValueError(f"GSI '{index_name}' is not defined on model {model_cls.__name__}")

        # Internal state of the scan
        self.limit_val: int | None = None
        self.index_name = index_name

        # Polymorphism support (internal discriminator filtering)
        self.filter_conditions: list[str] = []
        self.filter_values: dict[str, Any] = {}
        self.filter_names: dict[str, str] = {}

        # User-provided filter condition
        self.user_filter_condition: Condition | None = None

        # Auto-add discriminator filter for subclass scans
        if self.config.discriminator_value and self.config.discriminator_field:
            self._add_discriminator_filter()

    def _add_discriminator_filter(self) -> None:
        """Adds a filter expression for the discriminator value."""
        disc_field = self.config.discriminator_field
        disc_value = self.config.discriminator_value

        if disc_field is None or disc_value is None:
            return  # Should not happen, but for type safety

        self.filter_conditions.append("#disc = :disc_val")
        self.filter_names["#disc"] = disc_field
        self.filter_values[":disc_val"] = self.serializer.to_dynamo_value(disc_value)

    # --- SCAN OPTIONS ---

    def limit(self, count: int) -> "DynamoScanBuilder[T]":
        """Sets the maximum number of items to evaluate."""
        self.limit_val = count
        return self

    def using_index(self, index_name: str) -> "DynamoScanBuilder[T]":
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

    def filter(self, condition: "Condition") -> "DynamoScanBuilder[T]":
        """
        Adds a filter condition on any attributes.

        Multiple calls to filter() are combined with AND.
        Use & and | operators on Attr() for complex conditions.

        Args:
            condition: A DynCondition or boto3 condition object

        Usage:
            # Single filter
            Movie.scan().filter(Movie.rating >= 8.0).all()

            # Multiple filters (AND)
            (Movie.scan()
                .filter(Movie.rating >= 8.0)
                .filter(Movie.genres.contains("Drama"))
                .all())

            # Complex condition
            condition = (
                (Movie.rating >= 8.0) | (Movie.genres.contains("Sci-Fi"))
            )
            Movie.scan().filter(condition).all()
        """
        from .conditions import wrap_condition

        # Wrap the incoming condition to ensure it's a DynCondition
        new_condition = wrap_condition(condition)

        # Combine with existing user filter (AND)
        if self.user_filter_condition is not None:
            self.user_filter_condition = self.user_filter_condition & new_condition
        else:
            self.user_filter_condition = new_condition

        return self

    # --- EXECUTION STRATEGIES ---

    def __iter__(self) -> Iterator[T]:
        """
        Lazy Execution: The scan is sent to DynamoDB only when iteration starts.
        Uses a Paginator to automatically handle 'LastEvaluatedKey'.
        """
        # Build paginator kwargs
        kwargs: dict[str, Any] = {"TableName": self.config.table_name}
        if self.index_name:
            kwargs["IndexName"] = self.index_name
        if self.limit_val:
            kwargs["Limit"] = self.limit_val

        # Prepare filter expression (discriminator + user filters)
        if self.filter_conditions or self.user_filter_condition:
            filter_parts = []
            all_names = {**self.filter_names}
            all_values = {**self.filter_values}

            # Add discriminator filter
            if self.filter_conditions:
                filter_parts.extend(self.filter_conditions)

            # Add user filter
            if self.user_filter_condition:
                from .conditions import compile_condition

                user_filter_params = compile_condition(self.user_filter_condition, self.serializer)
                filter_parts.append(user_filter_params["ConditionExpression"])

                # Merge attribute names and values from user filter
                if "ExpressionAttributeNames" in user_filter_params:
                    all_names.update(user_filter_params["ExpressionAttributeNames"])
                if "ExpressionAttributeValues" in user_filter_params:
                    all_values.update(user_filter_params["ExpressionAttributeValues"])

            # Combine all filters with AND
            kwargs["FilterExpression"] = " AND ".join(filter_parts)
            kwargs["ExpressionAttributeNames"] = all_names
            kwargs["ExpressionAttributeValues"] = all_values

        # Execute with Pagination
        logger.info(
            "Starting scan iteration",
            extra={
                "table": self.config.table_name,
                "index": self.index_name,
                "has_filter": bool(self.filter_conditions or self.user_filter_condition),
                "limit": self.limit_val,
            },
        )

        with handle_dynamo_errors(table_name=self.config.table_name):
            paginator = self.client.get_paginator("scan")
            count = 0
            for page in paginator.paginate(**kwargs):
                for item in page["Items"]:
                    # Deserialize DynamoDB JSON -> Python Dict -> Pydantic Model
                    raw_data = self.serializer.from_dynamo(item)
                    # Use polymorphic deserialization
                    yield self.model_cls._deserialize_item(raw_data)
                    count += 1
                    # Stop if we've reached the desired limit
                    if self.limit_val and count >= self.limit_val:
                        return

    def all(self) -> list[T]:
        """
        Executes the scan and consumes the entire iterator into a list.
        WARNING: Can consume high memory for large datasets.
        """
        return list(self)

    def first(self) -> T | None:
        """
        Executes the scan fetching only the first result.
        Optimized: Forces Limit=1 to save Read Capacity Units (RCU).
        """
        if self.limit_val is None:
            self.limit_val = 1

        try:
            return next(iter(self))
        except StopIteration:
            return None

    def one(self) -> T:
        """
        Expects exactly one result. Raises ValueError if not found.
        """
        item = self.first()
        if item is None:
            raise ValueError("No items found for this scan")
        return item

    def page(self, start_key: dict[str, Any] | None = None) -> "PageResult[T]":
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
        from .pagination import PageResult

        # Build scan kwargs
        kwargs: dict[str, Any] = {"TableName": self.config.table_name}
        if self.index_name:
            kwargs["IndexName"] = self.index_name
        if self.limit_val:
            kwargs["Limit"] = self.limit_val

        # Prepare filter expression (discriminator + user filters)
        if self.filter_conditions or self.user_filter_condition:
            filter_parts = []
            all_names = {**self.filter_names}
            all_values = {**self.filter_values}

            # Add discriminator filter
            if self.filter_conditions:
                filter_parts.extend(self.filter_conditions)

            # Add user filter
            if self.user_filter_condition:
                from .conditions import compile_condition

                user_filter_params = compile_condition(self.user_filter_condition, self.serializer)
                filter_parts.append(user_filter_params["ConditionExpression"])

                # Merge attribute names and values from user filter
                if "ExpressionAttributeNames" in user_filter_params:
                    all_names.update(user_filter_params["ExpressionAttributeNames"])
                if "ExpressionAttributeValues" in user_filter_params:
                    all_values.update(user_filter_params["ExpressionAttributeValues"])

            # Combine all filters with AND
            kwargs["FilterExpression"] = " AND ".join(filter_parts)
            kwargs["ExpressionAttributeNames"] = all_names
            kwargs["ExpressionAttributeValues"] = all_values

        # Add ExclusiveStartKey if cursor provided
        if start_key:
            kwargs["ExclusiveStartKey"] = self.serializer.to_dynamo(start_key)

        # Execute single scan (NOT paginator)
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

        with handle_dynamo_errors(table_name=self.config.table_name):
            response = self.client.scan(**kwargs)

        # Deserialize items
        items = [
            self.model_cls._deserialize_item(self.serializer.from_dynamo(item))
            for item in response.get("Items", [])
        ]

        # Get cursor for next page
        raw_key = response.get("LastEvaluatedKey")
        cursor = self.serializer.from_dynamo(raw_key) if raw_key else None

        return PageResult(items=items, last_evaluated_key=cursor, count=len(items))
