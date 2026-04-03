"""Field descriptors for Dynantic model definitions.

Provides ``Key``, ``SortKey``, ``GSIKey``, ``GSISortKey``, ``TTL``,
and ``Discriminator`` field factories for defining DynamoDB table schemas.
"""

from typing import Any
from uuid import uuid4

from pydantic import Field


def Key(default: Any = ..., *, auto: bool = False, **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as a DynamoDB Primary Key (Partition Key).

    Usage:
        email: str = Key()
        item_id: UUID = Key(auto=True)  # Auto-generates UUID4

    Args:
        default: Default value for the field
        auto: If True, auto-generates a UUID4 on instantiation.
              Field should be typed as UUID. Cannot be combined with an explicit default.
        **kwargs: Additional Pydantic Field arguments
    """
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    json_schema_extra["_dynamo_pk"] = True

    if auto:
        if default is not ...:
            raise ValueError("Cannot use Key(auto=True) with an explicit default value")
        json_schema_extra["_dynamo_auto_uuid"] = True
        return Field(
            default_factory=uuid4,
            json_schema_extra=json_schema_extra,
            **kwargs,
        )

    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def SortKey(default: Any = ..., *, auto: bool = False, **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as a DynamoDB Sort Key.

    Args:
        default: Default value for the field
        auto: If True, auto-generates a UUID4 on instantiation.
              Field should be typed as UUID. Cannot be combined with an explicit default.
        **kwargs: Additional Pydantic Field arguments
    """
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    json_schema_extra["_dynamo_sk"] = True

    if auto:
        if default is not ...:
            raise ValueError("Cannot use SortKey(auto=True) with an explicit default value")
        json_schema_extra["_dynamo_auto_uuid"] = True
        return Field(
            default_factory=uuid4,
            json_schema_extra=json_schema_extra,
            **kwargs,
        )

    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def GSIKey(index_name: str, default: Any = ..., **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as a Global Secondary Index (GSI) Partition Key.

    Usage:
        customer_id: str = GSIKey(index_name="customer-index")

    Architectural Note:
    -------------------
    This function wraps the standard Pydantic Field. It injects a hidden flag
    ('_dynamo_gsi_pk') into 'json_schema_extra' along with the index name.
    The DynamoMeta metaclass will inspect this flag at class creation time to
    identify GSI partition keys and build the GSI metadata.

    Args:
        index_name: Name of the Global Secondary Index
        default: Default value for the field
        **kwargs: Additional Pydantic Field arguments

    Returns:
        Pydantic Field instance with GSI metadata
    """
    # Extract existing extra dict or create new one
    json_schema_extra = kwargs.pop("json_schema_extra", {})

    # Inject our internal flag with index name
    json_schema_extra["_dynamo_gsi_pk"] = index_name

    # Return a standard Pydantic Field.
    # The '...' (Ellipsis) is Pydantic's way of saying "Required field" if no default is provided.
    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def GSISortKey(index_name: str, default: Any = ..., **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as a Global Secondary Index (GSI) Sort Key.

    Usage:
        order_date: str = GSISortKey(index_name="status-date-index")

    Architectural Note:
    -------------------
    This function wraps the standard Pydantic Field. It injects a hidden flag
    ('_dynamo_gsi_sk') into 'json_schema_extra' along with the index name.
    The DynamoMeta metaclass will inspect this flag at class creation time to
    identify GSI sort keys and build the GSI metadata.

    Args:
        index_name: Name of the Global Secondary Index
        default: Default value for the field
        **kwargs: Additional Pydantic Field arguments

    Returns:
        Pydantic Field instance with GSI metadata
    """
    # Extract existing extra dict or create new one
    json_schema_extra = kwargs.pop("json_schema_extra", {})

    # Inject our internal flag with index name
    json_schema_extra["_dynamo_gsi_sk"] = index_name

    # Return a standard Pydantic Field.
    # The '...' (Ellipsis) is Pydantic's way of saying "Required field" if no default is provided.
    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def TTL(default: Any = ..., **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as the DynamoDB TTL (Time To Live) attribute.

    The field should be typed as `datetime` (auto-converted to epoch seconds)
    or `int` (passed through as epoch seconds).

    Usage:
        expires_at: datetime = TTL()

    Note:
        TTL must be enabled on the DynamoDB table separately (via Terraform/CLI).
        Dynantic only handles correct serialization of the field value.

    Args:
        default: Default value for the field
        **kwargs: Additional Pydantic Field arguments

    Returns:
        Pydantic Field instance with TTL metadata
    """
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    json_schema_extra["_dynamo_ttl"] = True
    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def Discriminator(default: Any = ..., **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as the discriminator for polymorphic models.

    The discriminator field is used in single-table design to differentiate
    between different entity types stored in the same table.

    Usage:
        entity_type: str = Discriminator()

    Architectural Note:
    -------------------
    This function wraps the standard Pydantic Field. It injects a hidden flag
    into json_schema_extra. The DynamoMeta metaclass will use this to:
    1. Identify which field holds the discriminator value
    2. Enable polymorphic deserialization in queries/scans

    Args:
        default: Default value for the field
        **kwargs: Additional Pydantic Field arguments

    Returns:
        Pydantic Field instance with discriminator metadata
    """
    # Extract existing extra dict or create new one
    json_schema_extra = kwargs.pop("json_schema_extra", {})

    # Inject our internal flag
    json_schema_extra["_dynamo_discriminator"] = True

    # Return a standard Pydantic Field.
    # The '...' (Ellipsis) is Pydantic's way of saying "Required field" if no default is provided.
    return Field(default, json_schema_extra=json_schema_extra, **kwargs)
