from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar

import boto3
from pydantic import BaseModel, ConfigDict

# We must inherit from Pydantic's internal metaclass to coexist with BaseModel
from pydantic._internal._model_construction import ModelMetaclass

if TYPE_CHECKING:
    from .conditions import Condition  # Avoid circular import
    from .pagination import PageResult
    from .scan import DynamoScanBuilder
    from .updates import UpdateAction, UpdateBuilder


from ._logging import logger, redact_key
from .config import GSIDefinition, ModelOptions
from .exceptions import handle_dynamo_errors
from .query import DynamoQueryBuilder
from .serializer import DynamoSerializer

# Generic TypeVar to allow methods like .get() to return the correct subclass type (User)
T = TypeVar("T", bound="DynamoModel")


class DynamoMeta(ModelMetaclass):
    """
    The Brain of the operation.
    It runs ONCE when the class is defined (imported), not when instantiated.
    """

    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any
    ) -> Any:
        # Check if this class has a Discriminator field
        has_discriminator = any(
            hasattr(value, "json_schema_extra")
            and isinstance(value.json_schema_extra, dict)
            and value.json_schema_extra.get("_dynamo_discriminator")
            for value in namespace.values()
            if hasattr(value, "json_schema_extra")
        )

        # For classes with discriminator, allow extra fields
        if has_discriminator:
            if "model_config" not in namespace:
                namespace["model_config"] = ConfigDict(extra="allow", populate_by_name=True)
            else:
                existing = namespace["model_config"]
                if hasattr(existing, "extra"):
                    existing.extra = "allow"
                else:
                    existing["extra"] = "allow"

        # 1. Create the Pydantic class normally
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        # For polymorphic base classes, modify model_config to allow extra fields
        if hasattr(new_cls, "_meta") and new_cls._meta.is_base_entity:
            # Metaclass modifies Pydantic's model_config dynamically - mypy can't track this
            new_cls.model_config = ConfigDict(extra="allow", populate_by_name=True)  # type: ignore[attr-defined]

        # Stop processing if it's the base DynamoModel class itself
        if name == "DynamoModel":
            return new_cls

        # Check if this is a registered subclass (has _pending_parent_model marker)
        parent_model = getattr(new_cls, "_pending_parent_model", None)
        discriminator_value = getattr(new_cls, "_pending_discriminator_value", None)

        if parent_model is not None:
            # This is a registered subclass - inherit from parent but track lineage
            parent_meta = parent_model._meta

            # Create a new ModelOptions for this subclass
            new_cls._meta = ModelOptions(  # type: ignore[attr-defined]
                table_name=parent_meta.table_name,
                pk_name=parent_meta.pk_name,
                sk_name=parent_meta.sk_name,
                region=parent_meta.region,
                gsi_definitions=parent_meta.gsi_definitions,
                discriminator_field=parent_meta.discriminator_field,
                entity_registry=parent_meta.entity_registry,  # Shared registry
                is_base_entity=False,
                parent_model=parent_model,
                discriminator_value=discriminator_value,
            )

            # Clean up temporary markers
            delattr(new_cls, "_pending_parent_model")
            delattr(new_cls, "_pending_discriminator_value")

            return new_cls

        # 2. Extract configuration from the inner 'Meta' class
        meta_cls = namespace.get("Meta")

        # Check if this inherits from a polymorphic base class
        polymorphic_base = None
        for base in bases:
            if hasattr(base, "_meta") and getattr(base._meta, "is_base_entity", False):
                polymorphic_base = base
                break

        if polymorphic_base and not meta_cls:
            # Inherit configuration from polymorphic base
            base_meta = polymorphic_base._meta
            new_cls._meta = ModelOptions(  # type: ignore[attr-defined]
                table_name=base_meta.table_name,
                pk_name=base_meta.pk_name,
                sk_name=base_meta.sk_name,
                region=base_meta.region,
                gsi_definitions=base_meta.gsi_definitions,
                discriminator_field=base_meta.discriminator_field,
                entity_registry=base_meta.entity_registry,
                is_base_entity=False,
                parent_model=polymorphic_base,
            )
            return new_cls

        # If no Meta, try to inherit from a base class
        if not meta_cls:
            for base in bases:
                if hasattr(base, "_meta"):
                    # Inherit configuration from base
                    base_meta = base._meta
                    new_cls._meta = ModelOptions(  # type: ignore[attr-defined]
                        table_name=base_meta.table_name,
                        pk_name=base_meta.pk_name,
                        sk_name=base_meta.sk_name,
                        region=base_meta.region,
                        gsi_definitions=base_meta.gsi_definitions,
                        discriminator_field=base_meta.discriminator_field,
                        entity_registry=base_meta.entity_registry,
                        is_base_entity=base_meta.is_base_entity,
                    )
                    return new_cls

            raise ValueError(f"Model {name} is missing a 'class Meta' with 'table_name'.")

        if not hasattr(meta_cls, "table_name"):
            raise ValueError(f"Model {name} is missing a 'table_name' in class Meta.")

        # 3. Scan fields to find Primary Key, Sort Key, Discriminator, and GSI definitions
        # We look for flags injected by fields.Key(), SortKey(), Discriminator(), etc.
        pk_name: str | None = None
        sk_name: str | None = None
        discriminator_field: str | None = None

        # Track GSI keys: {index_name: {"pk": field_name, "sk": field_name}}
        gsi_keys: dict[str, dict[str, str]] = {}

        # model_fields is a Pydantic attribute added at class creation - mypy sees incomplete type
        for field_name, field_info in new_cls.model_fields.items():  # type: ignore[attr-defined]
            extra = field_info.json_schema_extra
            if not extra:
                continue

            # Main table keys
            if extra.get("_dynamo_pk"):
                if pk_name is not None:
                    raise ValueError(f"Model {name} can have only one field defined with Key()")
                pk_name = field_name
            elif extra.get("_dynamo_sk"):
                if sk_name is not None:
                    raise ValueError(f"Model {name} can have only one field defined with SortKey()")
                sk_name = field_name

            # Discriminator field
            if extra.get("_dynamo_discriminator"):
                if discriminator_field is not None:
                    raise ValueError(f"Model {name} can have only one Discriminator() field")
                discriminator_field = field_name

            # GSI keys
            if "_dynamo_gsi_pk" in extra:
                index_name = extra["_dynamo_gsi_pk"]
                if index_name not in gsi_keys:
                    gsi_keys[index_name] = {}
                if "pk" in gsi_keys[index_name]:
                    raise ValueError(
                        f"GSI '{index_name}' in model {name} can have only one partition key"
                    )
                gsi_keys[index_name]["pk"] = field_name

            if "_dynamo_gsi_sk" in extra:
                index_name = extra["_dynamo_gsi_sk"]
                if index_name not in gsi_keys:
                    gsi_keys[index_name] = {}
                if "sk" in gsi_keys[index_name]:
                    raise ValueError(
                        f"GSI '{index_name}' in model {name} can have only one sort key"
                    )
                gsi_keys[index_name]["sk"] = field_name

        # If no PK found in current fields, try to inherit from base classes
        if not pk_name:
            # We skip `DynamoModel` itself and object
            for base in bases:
                if hasattr(base, "_meta") and isinstance(base._meta, ModelOptions):
                    # Inherit PK
                    pk_name = base._meta.pk_name
                    # Inherit SK only if not already found (subclass might define its own,
                    # but usually it's stable).
                    # If subclass defined SK, sk_name is not None.
                    # If subclass didn't define SK, we inherit it.
                    if sk_name is None:
                        sk_name = base._meta.sk_name

                    # We found a valid base configuration, stop looking
                    break

        if not pk_name:
            raise ValueError(f"Model {name} must have exactly one field defined with Key()")

        # 4. Build GSI definitions
        gsi_definitions: dict[str, GSIDefinition] = {}
        for index_name, keys in gsi_keys.items():
            if "pk" not in keys:
                raise ValueError(
                    f"GSI '{index_name}' in model {name} must have a partition key "
                    f"defined with GSIKey(index_name='{index_name}')"
                )
            gsi_definitions[index_name] = GSIDefinition(
                index_name=index_name,
                pk_name=keys["pk"],
                sk_name=keys.get("sk"),
            )

        # 5. Attach the processed configuration to the class
        # We use a protected attribute '_meta' to avoid colliding with user fields
        new_cls._meta = ModelOptions(  # type: ignore[attr-defined]
            table_name=meta_cls.table_name,
            pk_name=pk_name,
            sk_name=sk_name,
            region=getattr(meta_cls, "region", "us-east-1"),
            gsi_definitions=gsi_definitions,
            discriminator_field=discriminator_field,
            entity_registry={},  # Empty, will be populated by @register
            is_base_entity=discriminator_field is not None,
        )

        # For polymorphic base classes, modify model_config to allow extra fields
        if discriminator_field is not None:
            # Metaclass modifies Pydantic's model_config dynamically - mypy can't track this
            new_cls.model_config = ConfigDict(extra="allow", populate_by_name=True)  # type: ignore[attr-defined]

        # 6. Instrument class attributes for Query DSL
        # This replaces the Pydantic field descriptors on the class with Attr() builders
        # enabling the syntax: User.age >= 18
        # This does NOT affect instance attribute access, which still returns the values.
        from .conditions import Attr

        # model_fields is a Pydantic attribute added at class creation - mypy sees incomplete type
        for field_name, field_info in new_cls.model_fields.items():  # type: ignore[attr-defined]
            # Use the alias if defined (this is the actual DynamoDB attribute name)
            # or fall back to the field name
            dynamo_name = field_info.alias or field_name

            # Helper: Don't overwrite methods or existing properties if any (unlikely for fields)
            # but we force overwrite to ensure DSL works.
            setattr(new_cls, field_name, Attr(dynamo_name))

        return new_cls


class DynamoModel(BaseModel, metaclass=DynamoMeta):
    """
    The Base Class users will inherit from.
    Combines Pydantic validation with DynamoDB operations.
    """

    # Type Hinting for the configuration injected by Metaclass
    _meta: ClassVar[ModelOptions]

    # Internal utilities (Serializer & Client)
    # In a real async app, the client should be managed via dependency injection/lifespan
    _serializer: ClassVar[DynamoSerializer] = DynamoSerializer()
    _client: ClassVar[Any | None] = None
    _client_context: ClassVar[ContextVar[Any | None]] = ContextVar("dynamo_client", default=None)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @classmethod
    def _get_client(cls) -> Any:
        """
        Returns a Boto3 DynamoDB Client.
        Uses a singleton pattern to avoid multiple instantiations.

        Architectural Note:
        -------------------
        In a production async application, consider using aioboto3 and proper
        lifecycle management (startup/shutdown) to handle the client.

        Returns:
            Boto3 DynamoDB Client instance.
        """
        # 1. Check ContextVar (Thread-safe/Async-safe override)
        ctx_client = cls._client_context.get()
        if ctx_client is not None:
            return ctx_client

        # 2. Check Global Default (Backward compatibility)
        if cls._client is not None:
            return cls._client

        # 3. Initialize Default Global Client
        cls._client = boto3.client("dynamodb")
        return cls._client

    @classmethod
    @contextmanager
    def using_client(cls, client: Any) -> Generator[None, None, None]:
        """
        Context manager to properly scope a client to a block of code.
        Thread-safe and Async-safe using contextvars.

        Usage:
            with User.using_client(my_client):
                User.get("...")
        """
        token = cls._client_context.set(client)
        try:
            yield
        finally:
            cls._client_context.reset(token)

    @classmethod
    def set_client(cls, client: Any) -> None:
        """
        Allows injecting a custom Boto3/aioboto3 client.
        Useful for testing or advanced configurations.
        """
        cls._client = client  # Replace with aioboto3 for async

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

        # 3. Perform the fetch (Async in production)
        # For this prototype, we assume the client method is awaitable or wrapped
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
        # Reuses the class method logic passing its own keys
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
        # 'by_alias' ensures we respect field aliases if used
        data = self.model_dump(mode="python", exclude_none=True)

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
        # 5. Send to AWS
        client = self._get_client()

        # Log start
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
            # These are processed during subclass creation
            subclass._pending_parent_model = cls  # type: ignore[attr-defined]
            subclass._pending_discriminator_value = discriminator_value  # type: ignore[attr-defined]

            # Register the entity in the parent's registry
            cls._meta.register_entity(discriminator_value, subclass)

            # Update the subclass _meta to track its discriminator value
            if hasattr(subclass, "_meta"):
                subclass._meta.discriminator_value = discriminator_value
                subclass._meta.parent_model = cls

            # AUTO-INJECT: Set the discriminator field value on the subclass
            # This eliminates the need for manual field redefinition
            discriminator_field = cls._meta.discriminator_field
            if discriminator_field:
                # Set as class attribute (replaces Attr object from parent)
                setattr(subclass, discriminator_field, discriminator_value)

                # CRITICAL: Also update the annotation to ensure Pydantic uses the value
                if hasattr(subclass, "__annotations__"):
                    # Keep the annotation but ensure the default value is used
                    subclass.__annotations__[discriminator_field] = str

                # Update Pydantic's model_fields to use the discriminator value as default
                if (
                    hasattr(subclass, "model_fields")
                    and discriminator_field in subclass.model_fields
                ):
                    # Rebuild the field with the new default
                    from pydantic.fields import FieldInfo

                    # Create a new FieldInfo with the discriminator value as default
                    new_field = FieldInfo(
                        annotation=str,
                        default=discriminator_value,
                        default_factory=None,
                    )
                    subclass.model_fields[discriminator_field] = new_field

                    # Force Pydantic to rebuild the schema/validators
                    subclass.model_rebuild(force=True)

            return subclass

        return decorator

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
