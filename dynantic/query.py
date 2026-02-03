from collections.abc import Iterable, Iterator
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from ._logging import logger, redact_key
from .exceptions import handle_dynamo_errors

if TYPE_CHECKING:
    from .conditions import Condition
    from .pagination import PageResult

if TYPE_CHECKING:
    # Prevent circular imports at runtime
    from .base import DynamoModel

# We use a TypeVar bound to 'DynamoModel' to ensure
# that QueryBuilder returns the correct subclass (e.g., User, Message)
T = TypeVar("T", bound="DynamoModel")


class DynamoQueryBuilder(Iterable[T]):
    """
    Implements the Builder Pattern for DynamoDB Queries.
    Allows chaining methods (e.g., .between().limit().reverse())
    before executing the request.
    """

    def __init__(self, model_cls: type[T], pk_val: Any, index_name: str | None = None):
        self.model_cls = model_cls
        self.config = model_cls._meta
        self.client = model_cls._get_client()
        self.serializer = model_cls._serializer

        # Internal state of the query
        self.pk_val = pk_val
        self.sk_condition: str | None = None
        self.limit_val: int | None = None
        self.scan_forward = True
        self.index_name = index_name

        # Polymorphism support (internal discriminator filtering)
        self.filter_conditions: list[str] = []
        self.filter_values: dict[str, Any] = {}
        self.filter_names: dict[str, str] = {}

        # User-provided filter condition
        self.user_filter_condition: Condition | None = None

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
        # We immediately serialize the Partition Key value.
        self.expression_values: dict[str, Any] = {":pk": self.serializer.to_dynamo_value(pk_val)}

        # Prepare the Expression Attribute Names dictionary.
        # This is used to escape reserved keywords in DynamoDB.
        self.expression_names: dict[str, str] = {"#pk": self.pk_name}

        # Auto-add discriminator filter for subclass queries
        if self.config.discriminator_value and self.config.discriminator_field:
            self._add_discriminator_filter()

    def _serialize_query_value(self, value: Any) -> Any:
        """
        Convert Python values to DynamoDB-compatible format for query expressions.

        Handles datetime, UUID, Enum, and other complex types that need special
        serialization for use in KeyConditionExpression values.
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

    def _add_discriminator_filter(self) -> None:
        """Adds a filter expression for the discriminator value."""
        disc_field = self.config.discriminator_field
        disc_value = self.config.discriminator_value

        if disc_field is None or disc_value is None:
            return  # Should not happen, but for type safety

        self.filter_conditions.append("#disc = :disc_val")
        self.filter_names["#disc"] = disc_field
        self.filter_values[":disc_val"] = self.serializer.to_dynamo_value(disc_value)

    # --- KEY CONDITION METHODS (Builder Interface) ---

    def starts_with(self, prefix: Any) -> "DynamoQueryBuilder[T]":
        """Adds a 'begins_with' condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "begins_with(#sk, :sk)"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(prefix)
        )
        return self

    def between(self, low: Any, high: Any) -> "DynamoQueryBuilder[T]":
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

    def gt(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds a Greater Than (>) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk > :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    def lt(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds a Less Than (<) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk < :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    def ge(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds a Greater Than or Equal To (>=) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk >= :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    def le(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds a Less Than or Equal To (<=) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk <= :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    def eq(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds an Equal To (=) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk = :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    def ne(self, val: Any) -> "DynamoQueryBuilder[T]":
        """Adds a Not Equal To (<>) condition on the Sort Key."""
        if not self.sk_name:
            raise ValueError("Index does not have a Sort Key defined.")

        self.sk_condition = "#sk <> :sk"
        self.expression_names["#sk"] = self.sk_name
        self.expression_values[":sk"] = self.serializer.to_dynamo_value(
            self._serialize_query_value(val)
        )
        return self

    # --- QUERY OPTIONS ---

    def limit(self, count: int) -> "DynamoQueryBuilder[T]":
        """Sets the maximum number of items to evaluate."""
        self.limit_val = count
        return self

    def reverse(self) -> "DynamoQueryBuilder[T]":
        """
        Reverses the order of results.
        If True (default), Sort Key is ascending. If False, descending.
        """
        self.scan_forward = False
        return self

    def filter(self, condition: "Condition") -> "DynamoQueryBuilder[T]":
        """
        Adds a filter condition on non-key attributes.

        Multiple calls to filter() are combined with AND.
        Use & and | operators on Attr() for complex conditions.

        Args:
            condition: A DynCondition or boto3 condition object

        Usage:
            # Single filter
            Movie.query(2013).filter(Movie.rating >= 8.0).all()

            # Multiple filters (AND)
            (Movie.query(2013)
                .filter(Movie.rating >= 8.0)
                .filter(Movie.genres.contains("Drama"))
                .all())

            # Complex condition
            condition = (Movie.rating >= 8.0) | (Movie.genres.contains("Sci-Fi"))
            Movie.query(2013).filter(condition).all()

            # Filter with key condition
            (Movie.query(2013)
                .starts_with("Inter")
                .filter(Movie.rating < 8.5)
                .all())
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

    def using_index(self, index_name: str) -> "DynamoQueryBuilder[T]":
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

        # Update expression names for the new index
        self.expression_names["#pk"] = self.pk_name
        if self.sk_name and "#sk" in self.expression_names:
            self.expression_names["#sk"] = self.sk_name

        return self

    # --- EXECUTION STRATEGIES ---

    def __iter__(self) -> Iterator[T]:
        """
        Lazy Execution: The query is sent to DynamoDB only when iteration starts.
        Uses a Paginator to automatically handle 'LastEvaluatedKey'.
        """
        # 1. Construct the KeyConditionExpression using placeholders
        key_expr = "#pk = :pk"
        if self.sk_condition:
            key_expr += f" AND {self.sk_condition}"

        # 2. Prepare Boto3 arguments
        # Merge expression values and names
        all_values = {**self.expression_values, **self.filter_values}
        all_names = {**self.expression_names, **self.filter_names}

        kwargs = {
            "TableName": self.config.table_name,
            "KeyConditionExpression": key_expr,
            "ExpressionAttributeValues": all_values,
            "ExpressionAttributeNames": all_names,
            "ScanIndexForward": self.scan_forward,
        }

        if self.limit_val:
            kwargs["Limit"] = self.limit_val

        if self.index_name:
            kwargs["IndexName"] = self.index_name

        # Prepare filter expression (discriminator + user filters)
        if self.filter_conditions or self.user_filter_condition:
            filter_parts = []

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

        # 3. Execute with Pagination
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

        with handle_dynamo_errors(table_name=self.config.table_name):
            paginator = self.client.get_paginator("query")
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
        Executes the query and consumes the entire iterator into a list.
        WARNING: Can consume high memory for large datasets.
        """
        return list(self)

    def first(self) -> T | None:
        """
        Executes the query fetching only the first result.
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
            raise ValueError("No items found for this query")
        return item

    def page(self, start_key: dict[str, Any] | None = None) -> "PageResult[T]":
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
        from .pagination import PageResult

        # 1. Construct the KeyConditionExpression using placeholders
        key_expr = "#pk = :pk"
        if self.sk_condition:
            key_expr += f" AND {self.sk_condition}"

        # 2. Prepare Boto3 arguments
        # Merge expression values and names
        all_values = {**self.expression_values, **self.filter_values}
        all_names = {**self.expression_names, **self.filter_names}

        kwargs = {
            "TableName": self.config.table_name,
            "KeyConditionExpression": key_expr,
            "ExpressionAttributeValues": all_values,
            "ExpressionAttributeNames": all_names,
            "ScanIndexForward": self.scan_forward,
        }

        if self.limit_val:
            kwargs["Limit"] = self.limit_val

        if self.index_name:
            kwargs["IndexName"] = self.index_name

        # Prepare filter expression (discriminator + user filters)
        if self.filter_conditions or self.user_filter_condition:
            filter_parts = []

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

        # Add ExclusiveStartKey if cursor provided
        if start_key:
            kwargs["ExclusiveStartKey"] = self.serializer.to_dynamo(start_key)

        # Add ExclusiveStartKey if cursor provided
        if start_key:
            kwargs["ExclusiveStartKey"] = self.serializer.to_dynamo(start_key)

        # 3. Execute single query (NOT paginator)
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

        with handle_dynamo_errors(table_name=self.config.table_name):
            response = self.client.query(**kwargs)

        # 4. Deserialize items
        items = [
            self.model_cls._deserialize_item(self.serializer.from_dynamo(item))
            for item in response.get("Items", [])
        ]

        # 5. Get cursor for next page
        raw_key = response.get("LastEvaluatedKey")
        cursor = self.serializer.from_dynamo(raw_key) if raw_key else None

        return PageResult(items=items, last_evaluated_key=cursor, count=len(items))
