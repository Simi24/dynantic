from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from ._logging import logger, redact_key
from .builder import BaseBuilder

if TYPE_CHECKING:
    from typing_extensions import Self

    from .model import DynamoModel
    from .pagination import PageResult

T = TypeVar("T", bound="DynamoModel")


class DynamoQueryBuilder(BaseBuilder[T]):
    """
    Implements the Builder Pattern for DynamoDB Queries.
    Allows chaining methods (e.g., .between().limit().reverse())
    before executing the request.
    """

    def __init__(self, model_cls: type[T], pk_val: Any, index_name: str | None = None):
        super().__init__(model_cls, index_name)
        self._operation_name = "query"

        self.pk_val = pk_val
        self.sk_condition: str | None = None
        self.scan_forward = True

        # Determine which keys to use based on index
        if index_name:
            gsi = self.config.get_gsi(index_name)
            if not gsi:
                raise ValueError(f"GSI '{index_name}' is not defined on model {model_cls.__name__}")
            self.pk_name = gsi.pk_name
            self.sk_name = gsi.sk_name
        else:
            self.pk_name = self.config.pk_name
            self.sk_name = self.config.sk_name

        # Prepare the Expression Attribute Values dictionary.
        self.expression_values: dict[str, Any] = {":pk": self.serializer.to_dynamo_value(pk_val)}

        # Prepare the Expression Attribute Names dictionary.
        self.expression_names: dict[str, str] = {"#pk": self.pk_name}

    def _serialize_query_value(self, value: Any) -> Any:
        """
        Convert Python values to DynamoDB-compatible format for query expressions.
        """
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        return value

    # --- KEY CONDITION METHODS (Builder Interface) ---

    def starts_with(self, prefix: Any) -> Self:
        """Adds a 'begins_with' condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "begins_with(#sk, :sk)"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(prefix)
        )
        return self

    def between(self, low: Any, high: Any) -> Self:
        """Adds a 'BETWEEN' condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk BETWEEN :low AND :high"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":low"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(low)
        )
        self.expression_values[":high"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(high)
        )
        return self

    def gt(self, val: Any) -> Self:
        """Adds a Greater Than (>) condition on the Sort Key."""
        return self._sk_condition(">", val)

    def lt(self, val: Any) -> Self:
        """Adds a Less Than (<) condition on the Sort Key."""
        return self._sk_condition("<", val)

    def ge(self, val: Any) -> Self:
        """Adds a Greater Than or Equal To (>=) condition on the Sort Key."""
        return self._sk_condition(">=", val)

    def le(self, val: Any) -> Self:
        """Adds a Less Than or Equal To (<=) condition on the Sort Key."""
        return self._sk_condition("<=", val)

    def eq(self, val: Any) -> Self:
        """Adds an Equal To (=) condition on the Sort Key."""
        return self._sk_condition("=", val)

    def ne(self, val: Any) -> Self:
        """Adds a Not Equal To (<>) condition on the Sort Key."""
        return self._sk_condition("<>", val)

    def _sk_condition(self, operator: str, val: Any) -> Self:
        """Helper to set a sort key condition with the given operator."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = f"#sk {operator} :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    # --- QUERY OPTIONS ---

    def reverse(self) -> Self:
        """
        Reverses the order of results.
        If True (default), Sort Key is ascending. If False, descending.
        """
        self.scan_forward = False
        return self

    def using_index(self, index_name: str) -> Self:
        """
        Switches to querying a different index.
        This reinitializes the key names for the specified index.
        """
        gsi = self.config.get_gsi(index_name)
        if not gsi:
            raise ValueError(
                f"GSI '{index_name}' is not defined on model {self.model_cls.__name__}"
            )

        self.index_name = index_name
        self.pk_name = gsi.pk_name
        self.sk_name = gsi.sk_name

        self.expression_names["#pk"] = self.pk_name
        if self.sk_name and "#sk" in self.expression_names:
            self.expression_names["#sk"] = self.sk_name

        return self

    # --- EXECUTION ---

    def _build_query_kwargs(self) -> dict[str, Any]:
        """Builds the full kwargs dict for a DynamoDB query."""
        key_expr = "#pk = :pk"
        if self.sk_condition:
            key_expr += f" AND {self.sk_condition}"

        # Start with key condition names/values
        all_values = dict(self.expression_values)
        all_names = dict(self.expression_names)

        kwargs = self._build_base_kwargs()
        kwargs["KeyConditionExpression"] = key_expr
        kwargs["ScanIndexForward"] = self.scan_forward

        # Build filter and merge names/values
        filter_kwargs = self._build_filter_kwargs(
            existing_names=all_names, existing_values=all_values
        )

        if "FilterExpression" in filter_kwargs:
            kwargs["FilterExpression"] = filter_kwargs["FilterExpression"]
            kwargs["ExpressionAttributeNames"] = filter_kwargs["ExpressionAttributeNames"]
            kwargs["ExpressionAttributeValues"] = filter_kwargs["ExpressionAttributeValues"]
        else:
            kwargs["ExpressionAttributeNames"] = all_names
            kwargs["ExpressionAttributeValues"] = all_values

        return kwargs

    def __iter__(self) -> Iterator[T]:
        """
        Lazy Execution: The query is sent to DynamoDB only when iteration starts.
        Uses a Paginator to automatically handle 'LastEvaluatedKey'.
        """
        kwargs = self._build_query_kwargs()

        logger.info(
            "Starting query iteration",
            extra={
                "table": self.config.table_name,
                "index": self.index_name,
                "pk_hash": redact_key(self.pk_val),
                "has_filter": bool(self.filter_conditions),
                "limit": self.limit_val,
            },
        )

        yield from self._paginate_and_yield("query", kwargs)

    def page(self, start_key: dict[str, Any] | None = None) -> PageResult[T]:
        """
        Executes the query and returns a single page of results with cursor.

        Args:
            start_key: The LastEvaluatedKey from a previous page() call.
                       Pass None for the first page.

        Returns:
            PageResult containing items and the cursor for the next page.

        Usage:
            # First page
            page1 = Message.query("room-1").limit(10).page()

            # Next page
            if page1.has_more:
                page2 = Message.query("room-1").limit(10).page(start_key=page1.last_evaluated_key)
        """
        kwargs = self._build_query_kwargs()

        if start_key:
            kwargs["ExclusiveStartKey"] = self.serializer.to_dynamo(start_key)

        logger.info(
            "Executing query page",
            extra={
                "table": self.config.table_name,
                "index": self.index_name,
                "pk_hash": redact_key(self.pk_val),
                "has_filter": bool(self.filter_conditions),
                "limit": self.limit_val,
                "has_cursor": start_key is not None,
            },
        )

        return self._execute_page("query", kwargs)
