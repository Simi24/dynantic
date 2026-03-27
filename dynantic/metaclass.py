"""
Metaclass for Dynantic models.

DynamoMeta inspects model definitions at class creation time to extract
key configuration, GSI definitions, polymorphism setup, and condition DSL.
"""

from typing import Any

from pydantic import ConfigDict

# We must inherit from Pydantic's internal metaclass to coexist with BaseModel
from pydantic._internal._model_construction import ModelMetaclass

from .config import GSIDefinition, ModelOptions


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
                auto_uuid_fields=parent_meta.auto_uuid_fields,
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
                auto_uuid_fields=base_meta.auto_uuid_fields,
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
                        auto_uuid_fields=base_meta.auto_uuid_fields,
                        discriminator_field=base_meta.discriminator_field,
                        entity_registry=base_meta.entity_registry,
                        is_base_entity=base_meta.is_base_entity,
                    )
                    return new_cls

            raise ValueError(f"Model {name} is missing a 'class Meta' with 'table_name'.")

        if not hasattr(meta_cls, "table_name"):
            raise ValueError(f"Model {name} is missing a 'table_name' in class Meta.")

        # 3. Scan fields to find PK, SK, Discriminator, TTL, Auto-UUID, and GSI definitions
        pk_name: str | None = None
        sk_name: str | None = None
        discriminator_field: str | None = None
        ttl_field: str | None = None
        auto_uuid_fields: list[str] = []

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

            # TTL field
            if extra.get("_dynamo_ttl"):
                if ttl_field is not None:
                    raise ValueError(f"Model {name} can have only one TTL() field")
                # Validate type: must be datetime or int
                from datetime import datetime

                annotation = field_info.annotation
                if annotation not in (datetime, int):
                    raise ValueError(
                        f"TTL field '{field_name}' in model {name} must be typed as "
                        f"datetime or int, got {annotation}"
                    )
                ttl_field = field_name

            # Auto-UUID field
            if extra.get("_dynamo_auto_uuid"):
                from uuid import UUID

                annotation = field_info.annotation
                if annotation not in (UUID, str):
                    raise ValueError(
                        f"Auto-UUID field '{field_name}' in model {name} must be typed as "
                        f"UUID or str, got {annotation}"
                    )
                auto_uuid_fields.append(field_name)

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
            for base in bases:
                if hasattr(base, "_meta") and isinstance(base._meta, ModelOptions):
                    pk_name = base._meta.pk_name
                    if sk_name is None:
                        sk_name = base._meta.sk_name
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
        new_cls._meta = ModelOptions(  # type: ignore[attr-defined]
            table_name=meta_cls.table_name,
            pk_name=pk_name,
            sk_name=sk_name,
            region=getattr(meta_cls, "region", "us-east-1"),
            gsi_definitions=gsi_definitions,
            auto_uuid_fields=auto_uuid_fields,
            ttl_field=ttl_field,
            discriminator_field=discriminator_field,
            entity_registry={},  # Empty, will be populated by @register
            is_base_entity=discriminator_field is not None,
        )

        # For polymorphic base classes, modify model_config to allow extra fields
        if discriminator_field is not None:
            # Metaclass modifies Pydantic's model_config dynamically - mypy can't track this
            new_cls.model_config = ConfigDict(extra="allow", populate_by_name=True)  # type: ignore[attr-defined]

        # 6. Instrument class attributes for Query DSL
        from .conditions import Attr

        # model_fields is a Pydantic attribute added at class creation - mypy sees incomplete type
        for field_name, field_info in new_cls.model_fields.items():  # type: ignore[attr-defined]
            dynamo_name = field_info.alias or field_name
            setattr(new_cls, field_name, Attr(dynamo_name))

        return new_cls
