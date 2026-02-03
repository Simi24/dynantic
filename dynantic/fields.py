from typing import Any

from pydantic import Field


def Key(default: Any = ..., **kwargs: Any) -> Any:
    """
    Marks a Pydantic field as a DynamoDB Primary Key (Partition Key).

    Usage:
        email: str = Key()

    Architectural Note:
    -------------------
    This function wraps the standard Pydantic Field. It injects a hidden flag
    ('_dynamo_pk') into 'json_schema_extra'. The DynamoMeta metaclass will
    inspect this flag at class creation time to identify the primary key
    without requiring the user to explicitly define it in Config.
    """
    # Extract existing extra dict or create new one
    json_schema_extra = kwargs.pop("json_schema_extra", {})

    # Inject our internal flag
    json_schema_extra["_dynamo_pk"] = True

    # Return a standard Pydantic Field.
    # The '...' (Ellipsis) is Pydantic's way of saying "Required field" if no default is provided.
    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


def SortKey(default: Any = ..., **kwargs: Any) -> Any:
    """Marks a Pydantic field as a DynamoDB Sort Key."""
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    json_schema_extra["_dynamo_sk"] = True
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
