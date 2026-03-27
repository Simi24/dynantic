"""
DynamoModel — the base class users inherit from.

Combines Pydantic validation with DynamoDB CRUD operations,
query/scan entry points, and polymorphic model registration.
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .batch import BatchWriter
    from .conditions import Condition
    from .pagination import PageResult
    from .scan import DynamoScanBuilder
    from .updates import UpdateAction, UpdateBuilder

from ._logging import logger, redact_key
from .client import get_client, set_client, using_client
from .config import ModelOptions
from .exceptions import handle_dynamo_errors
from .metaclass import DynamoMeta
from .query import DynamoQueryBuilder
from .serializer import DynamoSerializer

# Generic TypeVar to allow methods like .get() to return the correct subclass type (User)
T = TypeVar("T", bound="DynamoModel")


class DynamoModel(BaseModel, metaclass=DynamoMeta):
    """
    The Base Class users will inherit from.
    Combines Pydantic validation with DynamoDB operations.
    """

    # Type Hinting for the configuration injected by Metaclass
    _meta: ClassVar[ModelOptions]

    # Internal utilities
    _serializer: ClassVar[DynamoSerializer] = DynamoSerializer()

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # ── Client Management ──────────────────────────────────────────

    @classmethod
    def _get_client(cls) -> Any:
        """Returns the active DynamoDB client (context-local or global)."""
        return get_client()

    @classmethod
    @contextmanager
    def using_client(cls, client: Any) -> Generator[None, None, None]:
        """
        Context manager to scope a client to a block of code.
        Thread-safe and Async-safe using contextvars.

        Usage:
            with User.using_client(my_client):
                User.get("...")
        """
        with using_client(client):
            yield

    @classmethod
    def set_client(cls, client: Any) -> None:
        """
        Allows injecting a custom Boto3/aioboto3 client.
        Useful for testing or advanced configurations.
        """
        set_client(client)

    # ── Transaction Operations ─────────────────────────────────────────

    @classmethod
    def transact_save(cls: type[T], items: list["DynamoModel"]) -> None:
        """
        Saves multiple items atomically. All items succeed or all fail.
        Items can be from different model classes (cross-table transactions).

        Args:
            items: List of model instances to save atomically

        Raises:
            TransactionConflictError: If the transaction conflicts or a condition fails
            ValidationError: If more than 100 items are provided

        Usage:
            DynamoModel.transact_save([user, order, log_entry])
        """
        from .transactions import TRANSACT_LIMIT, TransactPut

        if len(items) > TRANSACT_LIMIT:
            from .exceptions import ValidationError

            raise ValidationError(f"Transaction limit is {TRANSACT_LIMIT} items, got {len(items)}")

        actions = [TransactPut(item) for item in items]
        transact_items = [a._to_transact_item() for a in actions]

        client = cls._get_client()

        logger.info(
            "Transact save",
            extra={"item_count": len(items), "operation": "transact_save"},
        )

        with handle_dynamo_errors():
            client.transact_write_items(TransactItems=transact_items)

    @classmethod
    def transact_write(cls: type[T], actions: list[Any]) -> None:
        """
        Executes a list of write actions atomically.
        Supports TransactPut, TransactDelete, and TransactConditionCheck.

        Args:
            actions: List of TransactPut, TransactDelete, or TransactConditionCheck

        Raises:
            TransactionConflictError: If the transaction conflicts or a condition fails
            ValidationError: If more than 100 actions are provided

        Usage:
            from dynantic import TransactPut, TransactDelete, TransactConditionCheck

            DynamoModel.transact_write([
                TransactPut(user),
                TransactDelete(OldOrder, order_id="123"),
                TransactConditionCheck(User, Attr("status").eq("active"), user_id="u1"),
            ])
        """
        from .transactions import TRANSACT_LIMIT

        if len(actions) > TRANSACT_LIMIT:
            from .exceptions import ValidationError

            raise ValidationError(
                f"Transaction limit is {TRANSACT_LIMIT} actions, got {len(actions)}"
            )

        transact_items = [a._to_transact_item() for a in actions]

        client = cls._get_client()

        logger.info(
            "Transact write",
            extra={"action_count": len(actions), "operation": "transact_write"},
        )

        with handle_dynamo_errors():
            client.transact_write_items(TransactItems=transact_items)

    @classmethod
    def transact_get(cls: type[T], actions: list[Any]) -> list["DynamoModel | None"]:
        """
        Fetches multiple items atomically using TransactGetItems.
        Returns items in the same order as the input actions.

        Args:
            actions: List of TransactGet objects

        Returns:
            List of model instances (or None for missing items), in order

        Raises:
            TransactionConflictError: If the transaction conflicts
            ValidationError: If more than 100 actions are provided

        Usage:
            from dynantic import TransactGet

            results = DynamoModel.transact_get([
                TransactGet(User, user_id="u1"),
                TransactGet(Order, order_id="o1"),
            ])
        """
        from .transactions import TRANSACT_LIMIT

        if len(actions) > TRANSACT_LIMIT:
            from .exceptions import ValidationError

            raise ValidationError(
                f"Transaction limit is {TRANSACT_LIMIT} actions, got {len(actions)}"
            )

        transact_items = [a._to_transact_item() for a in actions]

        client = cls._get_client()

        logger.info(
            "Transact get",
            extra={"action_count": len(actions), "operation": "transact_get"},
        )

        with handle_dynamo_errors():
            response = client.transact_get_items(TransactItems=transact_items)

        results: list[DynamoModel | None] = []
        for i, resp_item in enumerate(response.get("Responses", [])):
            item_data = resp_item.get("Item")
            if item_data:
                model_cls = actions[i].model_cls
                raw_data = model_cls._serializer.from_dynamo(item_data)
                results.append(model_cls._deserialize_item(raw_data))
            else:
                results.append(None)

        return results

    # ── Batch Operations ─────────────────────────────────────────────

    @classmethod
    def batch_get(cls: type[T], keys: list[dict[str, Any]]) -> list[T]:
        """
        Fetches multiple items by their keys in a single batch request.
        Automatically chunks into groups of 100 and retries unprocessed keys.

        Args:
            keys: List of key dicts, e.g. [{"user_id": "u1"}, {"user_id": "u2"}]

        Returns:
            List of model instances (order not guaranteed by DynamoDB)

        Usage:
            users = User.batch_get([{"user_id": "u1"}, {"user_id": "u2"}])
        """
        from .batch import batch_get_with_retry

        client = cls._get_client()
        config = cls._meta

        dynamo_keys = [cls._serializer.to_dynamo(k) for k in keys]

        logger.info(
            "Batch get",
            extra={"table": config.table_name, "key_count": len(keys), "operation": "batch_get"},
        )

        with handle_dynamo_errors(table_name=config.table_name):
            raw_items = batch_get_with_retry(client, config.table_name, dynamo_keys)

        return [cls._deserialize_item(cls._serializer.from_dynamo(item)) for item in raw_items]

    @classmethod
    def batch_save(cls: type[T], items: list[T]) -> None:
        """
        Saves multiple items in a single batch request.
        Automatically chunks into groups of 25 and retries unprocessed items.

        Args:
            items: List of model instances to save

        Usage:
            User.batch_save([user1, user2, user3])
        """
        from .batch import batch_write_with_retry

        client = cls._get_client()
        config = cls._meta

        requests: list[dict[str, Any]] = []
        for item in items:
            data = item.model_dump(mode="python", exclude_none=True)
            # Handle TTL conversion
            if config.ttl_field and config.ttl_field in data:
                ttl_value = data[config.ttl_field]
                if isinstance(ttl_value, datetime):
                    data[config.ttl_field] = int(ttl_value.timestamp())
            dynamo_item = cls._serializer.to_dynamo(data)
            requests.append({"PutRequest": {"Item": dynamo_item}})

        logger.info(
            "Batch save",
            extra={"table": config.table_name, "item_count": len(items), "operation": "batch_save"},
        )

        with handle_dynamo_errors(table_name=config.table_name):
            batch_write_with_retry(client, config.table_name, requests)

    @classmethod
    def batch_delete(cls, keys: list[dict[str, Any]]) -> None:
        """
        Deletes multiple items by their keys in a single batch request.
        Automatically chunks into groups of 25 and retries unprocessed items.

        Args:
            keys: List of key dicts, e.g. [{"user_id": "u1"}, {"user_id": "u2"}]

        Usage:
            User.batch_delete([{"user_id": "u1"}, {"user_id": "u2"}])
        """
        from .batch import batch_write_with_retry

        client = cls._get_client()
        config = cls._meta

        requests: list[dict[str, Any]] = []
        for key in keys:
            dynamo_key = cls._serializer.to_dynamo(key)
            requests.append({"DeleteRequest": {"Key": dynamo_key}})

        logger.info(
            "Batch delete",
            extra={
                "table": config.table_name,
                "key_count": len(keys),
                "operation": "batch_delete",
            },
        )

        with handle_dynamo_errors(table_name=config.table_name):
            batch_write_with_retry(client, config.table_name, requests)

    @classmethod
    def batch_writer(cls: type[T]) -> "BatchWriter":
        """
        Returns a context manager for mixed batch put/delete operations.
        Auto-flushes at 25 items and on exit.

        Usage:
            with User.batch_writer() as batch:
                batch.save(user1)
                batch.save(user2)
                batch.delete(user_id="u3")
        """
        from .batch import BatchWriter

        return BatchWriter(cls, cls._get_client(), cls._serializer, cls._meta.table_name)

    # ── CRUD Operations ────────────────────────────────────────────

    @classmethod
    def get(cls: type[T], pk: Any, sk: Any | None = None) -> T | None:
        """
        Fetches an item by Primary Key.
        Returns an instance of the class (e.g., User) or None.

        Args:
            pk: Partition key value (any serializable type: str, int, UUID, etc.)
            sk: Sort key value (optional, any serializable type)
        """
        config = cls._meta

        # 1. Construct the Key dictionary
        key_dict = {config.pk_name: pk}
        if sk and config.sk_name:
            key_dict[config.sk_name] = sk

        # 2. Serialize key to Dynamo format (e.g. {'email': {'S': '...'}})
        dynamo_key = cls._serializer.to_dynamo(key_dict)

        # 3. Perform the fetch
        client = cls._get_client()

        logger.debug(
            "Fetching item",
            extra={
                "table": config.table_name,
                "key_hash": redact_key(key_dict),
                "operation": "get",
            },
        )

        with handle_dynamo_errors(table_name=config.table_name):
            response = client.get_item(TableName=config.table_name, Key=dynamo_key)

        if "Item" in response:
            logger.info(
                "Item found",
                extra={"table": config.table_name, "operation": "get", "pk_hash": redact_key(pk)},
            )
        else:
            logger.info(
                "Item not found",
                extra={"table": config.table_name, "operation": "get", "pk_hash": redact_key(pk)},
            )

        if "Item" not in response:
            return None

        # 4. Deserialize Dynamo JSON -> Python Dict -> Pydantic Model
        raw_data = cls._serializer.from_dynamo(response["Item"])
        return cls._deserialize_item(raw_data)

    @classmethod
    def delete(cls, pk: Any, sk: Any | None = None, condition: "Condition | None" = None) -> None:
        """
        Deletes an item by Primary Key (Class Method).
        Efficient because it doesn't require fetching the item first.

        Args:
            pk: Partition key value (any serializable type: str, int, UUID, etc.)
            sk: Sort key value (optional, any serializable type)
            condition: Optional condition that must be satisfied for the delete to succeed.
                       Accepts DynCondition or raw boto3 conditions.

        Raises:
            ConditionalCheckFailedError: If the condition is not satisfied

        Usage:
            User.delete("mario@test.com")

            # Delete only if version matches
            from dynantic import Attr
            User.delete("mario@test.com", condition=Attr("version") == 3)
        """
        config = cls._meta
        client = cls._get_client()

        # 1. Construct Key
        key_dict = {config.pk_name: pk}
        if sk and config.sk_name:
            key_dict[config.sk_name] = sk

        # 2. Serialize
        dynamo_key = cls._serializer.to_dynamo(key_dict)

        # 3. Build request kwargs
        kwargs: dict[str, Any] = {
            "TableName": config.table_name,
            "Key": dynamo_key,
        }

        # 4. Add condition expression if provided
        if condition is not None:
            from .conditions import compile_condition

            condition_params = compile_condition(condition, cls._serializer)
            kwargs.update(condition_params)

        # 5. Delete
        logger.info(
            "Deleting item",
            extra={
                "table": config.table_name,
                "operation": "delete",
                "key_hash": redact_key(key_dict),
                "has_condition": condition is not None,
            },
        )

        if condition is not None:
            logger.debug(
                "Delete condition details",
                extra={
                    "table": config.table_name,
                    "operation": "delete",
                    "condition_expression": kwargs.get("ConditionExpression"),
                },
            )

        with handle_dynamo_errors(table_name=config.table_name):
            client.delete_item(**kwargs)
            logger.info(
                "Delete successful", extra={"table": config.table_name, "operation": "delete"}
            )

    def delete_item(self, condition: "Condition | None" = None) -> None:
        """
        Deletes the current instance from DynamoDB.

        Args:
            condition: Optional condition that must be satisfied for the delete to succeed.
                       Accepts DynCondition or raw boto3 conditions.

        Usage:
            user = User.get("...")
            user.delete_item()

            # With condition
            from dynantic import Attr
            user.delete_item(condition=Attr("version") == user.version)
        """
        pk_val = getattr(self, self._meta.pk_name)
        sk_val = None
        if self._meta.sk_name:
            sk_val = getattr(self, self._meta.sk_name)

        self.delete(pk=pk_val, sk=sk_val, condition=condition)

    @classmethod
    def update(cls: type[T], pk: Any, sk: Any | None = None) -> "UpdateBuilder":
        """
        Starts an update builder chain for this item.

        Args:
            pk: Partition key value (any serializable type)
            sk: Sort key value (optional, any serializable type)

        Usage:
            User.update("email@example.com") \\
                .set(User.name, "New Name") \\
                .add(User.login_count, 1) \\
                .execute()
        """
        from .updates import UpdateBuilder

        return UpdateBuilder(cls, pk, sk)

    @classmethod
    def update_item(
        cls: type[T],
        key: dict[str, Any],
        actions: list["UpdateAction"],
        condition: "Condition | None" = None,
        return_values: Literal["NONE", "ALL_OLD", "UPDATED_OLD", "ALL_NEW", "UPDATED_NEW"] = "NONE",
    ) -> Any:
        """
        Convenience method to perform updates in one call.
        Useful when you have a list of pre-built actions.

        Args:
            key: Dictionary containing pk (and sk if needed)
            actions: List of UpdateAction objects (Set, Add, Remove, Delete)
            condition: condition to apply
            return_values: DynamoDB ReturnValues option

        Usage:
            User.update_item(
                key={"pk": "user123"},
                actions=[
                    Set(User.name, "New Name"),
                    Add(User.count, 1)
                ],
                return_values="ALL_NEW"
            )
        """
        from .updates import UpdateBuilder

        # Extract pk/sk from key dict
        pk = key.get(cls._meta.pk_name)
        if not pk:
            raise ValueError(f"Key missing partition key '{cls._meta.pk_name}'")

        sk = None
        if cls._meta.sk_name:
            sk = key.get(cls._meta.sk_name)

        builder = UpdateBuilder(cls, pk, sk)
        builder.actions = actions
        if condition:
            builder.condition(condition)
        builder.return_values(return_values)

        return builder.execute()

    def patch(self: T) -> "UpdateBuilder":
        """
        Starts an update builder chain for this item.

        Usage:
            user = User.get("email@example.com")
            user.patch() \\
                .set(User.name, "New Name") \\
                .add(User.login_count, 1) \\
                .execute()
        """
        from .updates import UpdateBuilder

        pk_val = getattr(self, self._meta.pk_name)
        sk_val = getattr(self, self._meta.sk_name) if self._meta.sk_name else None

        return UpdateBuilder(self.__class__, pk_val, sk_val)

    # ── Query & Scan ───────────────────────────────────────────────

    @classmethod
    def scan(cls: type[T], index_name: str | None = None) -> "DynamoScanBuilder[T]":
        """
        Returns a scan builder for chainable scan operations.

        Args:
            index_name: Optional GSI name to scan instead of main table

        Returns:
            DynamoScanBuilder for method chaining

        Usage:
            # Basic scan
            for user in User.scan():
                print(user.email)

            # Scan with filter
            for user in User.scan().filter(User.age >= 18):
                print(user.email)

            # Scan GSI with filter and limit
            high_rated = (Movie.scan(index_name="rating-index")
                .filter(Movie.rating >= 8.0)
                .limit(10)
                .all())
        """
        from .scan import DynamoScanBuilder

        return DynamoScanBuilder(cls, index_name=index_name)

    def save(self, condition: "Condition | None" = None) -> None:
        """
        Persists the current instance to DynamoDB.

        Args:
            condition: Optional condition that must be satisfied for the write to succeed.
                       Use Attr() to build conditions. Accepts DynCondition or raw boto3 conditions.

        Raises:
            ConditionalCheckFailedError: If the condition is not satisfied

        Usage:
            # Simple save (no condition)
            user.save()

            # Create-if-not-exists
            from dynantic import Attr
            user.save(condition=Attr("email").not_exists())

            # Optimistic locking
            user.save(condition=Attr("version") == old_version)
        """
        config = self._meta

        # 1. Dump Pydantic model to dict (preserving types like Sets for serializer)
        data = self.model_dump(mode="python", exclude_none=True)

        # 1b. Convert TTL field to epoch seconds if present
        if config.ttl_field and config.ttl_field in data:
            ttl_value = data[config.ttl_field]
            if isinstance(ttl_value, datetime):
                data[config.ttl_field] = int(ttl_value.timestamp())

        # 2. Convert to DynamoDB Format (handling Floats -> Decimals)
        dynamo_item = self._serializer.to_dynamo(data)

        # 3. Build request kwargs
        kwargs: dict[str, Any] = {
            "TableName": config.table_name,
            "Item": dynamo_item,
        }

        # 4. Add condition expression if provided
        if condition is not None:
            from .conditions import compile_condition

            condition_params = compile_condition(condition, self._serializer)
            kwargs.update(condition_params)

        # 5. Send to AWS
        client = self._get_client()

        pk_val = getattr(self, config.pk_name)
        logger.info(
            "Saving item",
            extra={
                "table": config.table_name,
                "operation": "save",
                "pk_hash": redact_key(pk_val),
                "has_condition": condition is not None,
            },
        )

        if condition is not None:
            logger.debug(
                "Save condition details",
                extra={
                    "table": config.table_name,
                    "operation": "save",
                    "condition_expression": kwargs.get("ConditionExpression"),
                },
            )

        with handle_dynamo_errors(table_name=config.table_name):
            client.put_item(**kwargs)
            logger.info("Save successful", extra={"table": config.table_name, "operation": "save"})

    @classmethod
    def query(cls: type[T], pk_val: Any) -> DynamoQueryBuilder[T]:
        """
        Starts a Query Builder chain.

        Usage:
            User.query("mario").starts_with("2023").limit(5).all()
        """
        return DynamoQueryBuilder(cls, pk_val)

    @classmethod
    def query_index(cls: type[T], index_name: str, pk_val: Any) -> DynamoQueryBuilder[T]:
        """
        Starts a Query Builder chain for a Global Secondary Index.

        Args:
            index_name: Name of the GSI to query
            pk_val: Partition key value for the GSI

        Usage:
            Order.query_index("customer-index", "CUST-123").all()

        Raises:
            ValueError: If the GSI is not defined on the model
        """
        if not cls._meta.has_gsi(index_name):
            raise ValueError(
                f"GSI '{index_name}' is not defined on model {cls.__name__}. "
                f"Available GSIs: {list(cls._meta.gsi_definitions.keys())}"
            )
        return DynamoQueryBuilder(cls, pk_val, index_name=index_name)

    # ── Polymorphism ───────────────────────────────────────────────

    @classmethod
    def register(cls, discriminator_value: str) -> Any:
        """
        Decorator to register a subclass as an entity type for polymorphic deserialization.

        The discriminator field value is automatically injected, so you don't need to
        redefine it in the subclass.

        Usage:
            @MyTable.register("USER")
            class User(MyTable):
                # discriminator field auto-injected
                name: str

        Args:
            discriminator_value: The value of the discriminator field for this entity type

        Returns:
            Decorator function that registers the subclass

        Raises:
            ValueError: If the base class doesn't have a discriminator field
            ValueError: If the subclass doesn't inherit from the base class
            ValueError: If the discriminator value is already registered
        """
        if not cls._meta.is_polymorphic():
            raise ValueError(
                f"Cannot register entities on {cls.__name__}: "
                f"it does not have a Discriminator() field"
            )

        def decorator(subclass: type[T]) -> type[T]:
            # Validate inheritance
            if not issubclass(subclass, cls):
                raise ValueError(
                    f"{subclass.__name__} must inherit from {cls.__name__} to be registered"
                )

            # Set temporary markers for the metaclass to pick up
            subclass._pending_parent_model = cls  # type: ignore[attr-defined]
            subclass._pending_discriminator_value = discriminator_value  # type: ignore[attr-defined]

            # Register the entity in the parent's registry
            cls._meta.register_entity(discriminator_value, subclass)

            # Update the subclass _meta to track its discriminator value
            if hasattr(subclass, "_meta"):
                subclass._meta.discriminator_value = discriminator_value
                subclass._meta.parent_model = cls

            # AUTO-INJECT: Set the discriminator field value on the subclass
            discriminator_field = cls._meta.discriminator_field
            if discriminator_field:
                setattr(subclass, discriminator_field, discriminator_value)

                if hasattr(subclass, "__annotations__"):
                    subclass.__annotations__[discriminator_field] = str

                if (
                    hasattr(subclass, "model_fields")
                    and discriminator_field in subclass.model_fields
                ):
                    from pydantic.fields import FieldInfo

                    new_field = FieldInfo(
                        annotation=str,
                        default=discriminator_value,
                        default_factory=None,
                    )
                    subclass.model_fields[discriminator_field] = new_field
                    subclass.model_rebuild(force=True)

            return subclass

        return decorator

    # ── Scan Page (legacy convenience) ─────────────────────────────

    @classmethod
    def scan_page(
        cls: type[T],
        limit: int | None = None,
        start_key: dict[str, Any] | None = None,
        index_name: str | None = None,
    ) -> "PageResult[T]":
        """
        Scans a single page of the table with explicit pagination control.

        Args:
            limit: Maximum number of items to return in this page
            start_key: The LastEvaluatedKey from a previous scan_page() call
            index_name: Optional GSI name to scan

        Returns:
            PageResult containing items and the cursor for the next page.

        Usage:
            # First page
            page1 = User.scan_page(limit=25)

            # Next page
            if page1.has_more:
                page2 = User.scan_page(limit=25, start_key=page1.last_evaluated_key)
        """
        from .pagination import PageResult

        config = cls._meta
        client = cls._get_client()

        # Validate GSI if specified
        if index_name and not config.has_gsi(index_name):
            raise ValueError(f"GSI '{index_name}' is not defined on model {cls.__name__}")

        # Build scan kwargs
        kwargs: dict[str, Any] = {"TableName": config.table_name}
        if index_name:
            kwargs["IndexName"] = index_name
        if limit:
            kwargs["Limit"] = limit

        # If this is a registered subclass, add filter for discriminator
        if config.discriminator_value and config.discriminator_field:
            kwargs["FilterExpression"] = "#disc = :disc_val"
            kwargs["ExpressionAttributeNames"] = {"#disc": config.discriminator_field}
            kwargs["ExpressionAttributeValues"] = {
                ":disc_val": cls._serializer.to_dynamo_value(config.discriminator_value)
            }

        # Add ExclusiveStartKey if cursor provided
        if start_key:
            kwargs["ExclusiveStartKey"] = cls._serializer.to_dynamo(start_key)

        logger.info(
            "Scanning page",
            extra={
                "table": config.table_name,
                "limit": limit,
                "has_cursor": start_key is not None,
                "operation": "scan_page",
            },
        )

        # Execute single scan (NOT paginator)
        with handle_dynamo_errors(table_name=config.table_name):
            response = client.scan(**kwargs)

        # Deserialize items
        items = [
            cls._deserialize_item(cls._serializer.from_dynamo(item))
            for item in response.get("Items", [])
        ]

        # Get cursor for next page
        raw_key = response.get("LastEvaluatedKey")
        cursor = cls._serializer.from_dynamo(raw_key) if raw_key else None

        return PageResult(items=items, last_evaluated_key=cursor, count=len(items))

    # ── Deserialization ────────────────────────────────────────────

    @classmethod
    def _deserialize_item(cls: type[T], raw_data: dict[str, Any]) -> T:
        """
        Deserializes a DynamoDB item to the correct model type.

        For polymorphic models, uses the discriminator field to determine
        the correct subclass to instantiate.

        Args:
            raw_data: Deserialized Python dict from DynamoDB

        Returns:
            Instance of the correct model type
        """
        config = cls._meta

        # Convert TTL epoch seconds back to datetime if needed
        if config.ttl_field and config.ttl_field in raw_data:
            ttl_value = raw_data[config.ttl_field]
            # Check if the model expects datetime but we got an int/Decimal (epoch)
            field_info = cls.model_fields.get(config.ttl_field)
            is_datetime_field = field_info and field_info.annotation is datetime
            if is_datetime_field and isinstance(ttl_value, (int, float)):
                from datetime import timezone

                raw_data[config.ttl_field] = datetime.fromtimestamp(int(ttl_value), tz=timezone.utc)

        # If this is a polymorphic base class, look up the correct subclass
        if config.is_base_entity and config.discriminator_field:
            discriminator_value = raw_data.get(config.discriminator_field)

            if discriminator_value:
                entity_class = config.get_entity_class(discriminator_value)
                if entity_class:
                    # entity_class is dynamically registered - mypy can't verify it's a T subclass
                    return entity_class(**raw_data)  # type: ignore[no-any-return]

            # Fall back to base class if discriminator not found/registered
            return cls(**raw_data)

        # Non-polymorphic or subclass: just instantiate
        return cls(**raw_data)
