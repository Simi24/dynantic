"""
Base builder for DynamoDB query and scan operations.

Extracts shared logic (filtering, pagination, terminal methods)
from DynamoQueryBuilder and DynamoScanBuilder.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from typing_extensions import Self

    from .conditions import Condition
    from .model import DynamoModel
    from .pagination import PageResult

from .exceptions import handle_dynamo_errors

T = TypeVar("T", bound="DynamoModel")


class BaseBuilder(Iterable[T]):
    """
    Shared base for DynamoQueryBuilder and DynamoScanBuilder.

    Provides common state (model, client, serializer, filters),
    filter composition, discriminator handling, terminal methods,
    and deserialization helpers.
    """

    def __init__(self, model_cls: type[T], index_name: str | None = None) -> None:
        self.model_cls = model_cls
        self.config = model_cls._meta
        self.client = model_cls._get_client()
        self.serializer = model_cls._serializer

        self.limit_val: int | None = None
        self.index_name = index_name
        self._operation_name = "operation"  # Overridden by subclasses

        # Discriminator filtering (internal)
        self.filter_conditions: list[str] = []
        self.filter_values: dict[str, Any] = {}
        self.filter_names: dict[str, str] = {}

        # User-provided filter condition
        self.user_filter_condition: Condition | None = None

        # Auto-add discriminator filter for subclass operations
        if self.config.discriminator_value and self.config.discriminator_field:
            self._add_discriminator_filter()

    def _add_discriminator_filter(self) -> None:
        """Adds a filter expression for the discriminator value."""
        disc_field = self.config.discriminator_field
        disc_value = self.config.discriminator_value

        if disc_field is None or disc_value is None:
            return

        self.filter_conditions.append("#disc = :disc_val")
        self.filter_names["#disc"] = disc_field
        self.filter_values[":disc_val"] = self.serializer.to_dynamo_value(disc_value)

    # ── Shared builder methods ─────────────────────────────────────

    def limit(self, count: int) -> Self:
        """Sets the maximum number of items to evaluate."""
        self.limit_val = count
        return self

    def filter(self, condition: Condition) -> Self:
        """
        Adds a filter condition on non-key attributes.

        Multiple calls to filter() are combined with AND.
        Use & and | operators on Attr() for complex conditions.

        Args:
            condition: A DynCondition or boto3 condition object
        """
        from .conditions import wrap_condition

        new_condition = wrap_condition(condition)

        if self.user_filter_condition is not None:
            self.user_filter_condition = self.user_filter_condition & new_condition
        else:
            self.user_filter_condition = new_condition

        return self

    # ── Terminal methods ───────────────────────────────────────────

    def all(self) -> list[T]:
        """
        Executes the operation and consumes the entire iterator into a list.
        WARNING: Can consume high memory for large datasets.
        """
        return list(self)

    def first(self) -> T | None:
        """
        Executes the operation fetching only the first result.
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
            raise ValueError(f"No items found for this {self._operation_name}")
        return item

    # ── Helpers ────────────────────────────────────────────────────

    def _build_filter_kwargs(
        self,
        existing_names: dict[str, str] | None = None,
        existing_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Builds filter expression kwargs from discriminator + user filters.

        Args:
            existing_names: Expression attribute names to merge with (e.g., from key conditions)
            existing_values: Expression attribute values to merge with

        Returns:
            Dict with FilterExpression, ExpressionAttributeNames, ExpressionAttributeValues
            to merge into the request kwargs.
        """
        if not self.filter_conditions and not self.user_filter_condition:
            return {}

        filter_parts: list[str] = []
        all_names = dict(existing_names or {})
        all_values = dict(existing_values or {})

        # Merge discriminator filter state
        all_names.update(self.filter_names)
        all_values.update(self.filter_values)

        if self.filter_conditions:
            filter_parts.extend(self.filter_conditions)

        if self.user_filter_condition:
            from .conditions import compile_condition

            user_filter_params = compile_condition(self.user_filter_condition, self.serializer)
            filter_parts.append(user_filter_params["ConditionExpression"])

            if "ExpressionAttributeNames" in user_filter_params:
                all_names.update(user_filter_params["ExpressionAttributeNames"])
            if "ExpressionAttributeValues" in user_filter_params:
                all_values.update(user_filter_params["ExpressionAttributeValues"])

        result: dict[str, Any] = {"FilterExpression": " AND ".join(filter_parts)}
        if all_names:
            result["ExpressionAttributeNames"] = all_names
        if all_values:
            result["ExpressionAttributeValues"] = all_values
        return result

    def _build_base_kwargs(self) -> dict[str, Any]:
        """Builds common kwargs shared by query and scan operations."""
        kwargs: dict[str, Any] = {"TableName": self.config.table_name}
        if self.index_name:
            kwargs["IndexName"] = self.index_name
        if self.limit_val:
            kwargs["Limit"] = self.limit_val
        return kwargs

    def _paginate_and_yield(self, operation: str, kwargs: dict[str, Any]) -> Iterator[T]:
        """
        Executes a paginated operation and yields deserialized items.

        Args:
            operation: "query" or "scan"
            kwargs: Full kwargs dict for the boto3 operation
        """
        with handle_dynamo_errors(table_name=self.config.table_name):
            paginator = self.client.get_paginator(operation)
            count = 0
            for page in paginator.paginate(**kwargs):
                for item in page["Items"]:
                    raw_data = self.serializer.from_dynamo(item)
                    yield self.model_cls._deserialize_item(raw_data)
                    count += 1
                    if self.limit_val and count >= self.limit_val:
                        return

    def _execute_page(self, operation: str, kwargs: dict[str, Any]) -> PageResult[T]:
        """
        Executes a single-page operation and returns a PageResult.

        Args:
            operation: "query" or "scan"
            kwargs: Full kwargs dict for the boto3 operation
        """
        from .pagination import PageResult

        with handle_dynamo_errors(table_name=self.config.table_name):
            response = getattr(self.client, operation)(**kwargs)

        items = [
            self.model_cls._deserialize_item(self.serializer.from_dynamo(item))
            for item in response.get("Items", [])
        ]

        raw_key = response.get("LastEvaluatedKey")
        cursor = self.serializer.from_dynamo(raw_key) if raw_key else None

        return PageResult(items=items, last_evaluated_key=cursor, count=len(items))

    def __iter__(self) -> Iterator[T]:
        raise NotImplementedError
