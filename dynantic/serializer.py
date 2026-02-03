from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, cast
from uuid import UUID

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from .exceptions import DynamoSerializationError


class DynamoSerializer:
    """
    Handles the conversion between Pydantic/Python types and DynamoDB Low-Level format.

    Architectural Note:
    -------------------
    DynamoDB requires numbers to be passed as 'Decimal' to avoid precision loss.
    Pydantic uses 'float'. Boto3's TypeSerializer throws an error if it encounters a float.
    This class acts as a Middleware to recursively convert Python types to DynamoDB-safe
    types before passing them to Boto3, and vice versa on retrieval.
    """

    def __init__(self) -> None:
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    def to_dynamo(self, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Converts a standard Python dict to DynamoDB JSON format ({"S": "...", "N": "..."})."""
        clean_data = self._prepare_for_dynamo(data)
        result = {}

        for k, v in clean_data.items():
            try:
                # TypeSerializer expects a single value, so we wrap/unwrap or map the dict
                serialized = self._serializer.serialize(v)
            except TypeError as e:
                # Catch unsupported types (e.g. custom classes, nested dicts with invalid types)
                raise DynamoSerializationError(
                    f"Failed to serialize field '{k}'. value={v!r} error={e!s}", original_error=e
                ) from e

            if not (isinstance(v, (set, frozenset)) and len(v) == 0):
                result[k] = cast(dict[str, Any], serialized)
        return result

    def to_dynamo_value(self, value: Any) -> dict[str, Any]:
        """
        Serializes a single scalar value to DynamoDB format.
        Useful for building ExpressionAttributeValues in queries.
        E.g.: 10.5 -> {'N': '10.5'}
        """
        clean_value = self._prepare_for_dynamo(value)
        try:
            result = cast(dict[str, Any], self._serializer.serialize(clean_value))
        except TypeError as e:
            raise DynamoSerializationError(
                f"Failed to serialize value '{value}'. error={e!s}", original_error=e
            ) from e
        return result

    def from_dynamo(self, item: dict[str, Any]) -> dict[str, Any]:
        """Converts DynamoDB JSON format back to standard Python dict."""
        python_data = {k: self._deserializer.deserialize(v) for k, v in item.items()}
        result = self._restore_to_python(python_data)
        assert isinstance(result, dict)
        return result

    def serialize_cursor(self, last_evaluated_key: dict[str, Any]) -> dict[str, Any]:
        """
        Converts DynamoDB LastEvaluatedKey format to plain Python dict.
        Used for returning cursor to frontend.

        Input:  {"pk": {"S": "value"}, "sk": {"N": "123"}}
        Output: {"pk": "value", "sk": 123}
        """
        return self.from_dynamo(last_evaluated_key)

    def deserialize_cursor(self, cursor: dict[str, Any]) -> dict[str, Any]:
        """
        Converts plain Python dict back to DynamoDB key format.
        Used for accepting cursor from frontend.

        Input:  {"pk": "value", "sk": 123}
        Output: {"pk": {"S": "value"}, "sk": {"N": "123"}}
        """
        return self.to_dynamo(cursor)

    def _prepare_for_dynamo(self, value: Any) -> Any:
        """
        Recursively prepares Python values for Boto3 TypeSerializer.

        Converts:
        - float -> Decimal (boto3 requirement)
        - datetime/date -> ISO 8601 string
        - UUID -> string
        - Enum -> value
        - set/frozenset -> list (DynamoDB doesn't support empty sets)
        """
        if isinstance(value, float):
            # Convert to string first to avoid float precision artifacts during Decimal creation
            return Decimal(str(value))
        if isinstance(value, datetime):
            # Convert datetime to ISO 8601 string using Pydantic's format
            # Pydantic uses 'Z' for UTC instead of '+00:00'
            utc_offset = value.utcoffset()
            if utc_offset is not None and utc_offset.total_seconds() == 0:
                # UTC timezone - use 'Z' suffix like Pydantic does
                return value.replace(tzinfo=None).isoformat() + "Z"
            else:
                # Non-UTC or naive datetime - use standard isoformat
                return value.isoformat()
        if isinstance(value, date):
            # Convert date to ISO 8601 string
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, bytes):
            # Bytes are supported by boto3, no conversion needed
            return value
        if isinstance(value, (set, frozenset)):
            # Keep as set for SS/NS/BS support (needed for atomic ADD/DELETE)
            # Warning: Empty sets will raise an error in boto3 TypeSerializer
            return {self._prepare_for_dynamo(v) for v in value}
        if isinstance(value, list):
            return [self._prepare_for_dynamo(v) for v in value]
        if isinstance(value, dict):
            return {k: self._prepare_for_dynamo(v) for k, v in value.items()}
        return value

    def _restore_to_python(self, value: Any) -> Any:
        """
        Recursively restores DynamoDB values to Python-friendly types.

        Converts:
        - Decimal -> int (if whole number) or float
        """
        if isinstance(value, Decimal):
            if value % 1 == 0:
                return int(value)
            return float(value)
        if isinstance(value, list):
            return [self._restore_to_python(v) for v in value]
        if isinstance(value, dict):
            return {k: self._restore_to_python(v) for k, v in value.items()}
        return value
