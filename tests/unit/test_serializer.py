"""
Unit tests for DynamoSerializer.

Tests serialization and deserialization between Python types and DynamoDB format.
"""

from typing import Any

import pytest

from dynantic.exceptions import DynamoSerializationError
from dynantic.serializer import DynamoSerializer


@pytest.mark.unit
class TestDynamoSerializerToDynamo:
    """Test serialization from Python to DynamoDB format."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_to_dynamo_string(self) -> None:
        """Test string serialization."""
        data = {"name": "Alice"}
        result = self.serializer.to_dynamo(data)
        assert result == {"name": {"S": "Alice"}}

    def test_to_dynamo_integer(self) -> None:
        """Test integer serialization."""
        data = {"age": 25}
        result = self.serializer.to_dynamo(data)
        assert result == {"age": {"N": "25"}}

    def test_to_dynamo_float(self) -> None:
        """Test float serialization (converted to Decimal)."""
        data = {"score": 95.5}
        result = self.serializer.to_dynamo(data)
        assert result == {"score": {"N": "95.5"}}

    def test_to_dynamo_boolean(self) -> None:
        """Test boolean serialization."""
        data = {"active": True}
        result = self.serializer.to_dynamo(data)
        assert result == {"active": {"BOOL": True}}

    def test_to_dynamo_list(self) -> None:
        """Test list serialization."""
        data = {"tags": ["python", "testing"]}
        result = self.serializer.to_dynamo(data)
        assert result == {"tags": {"L": [{"S": "python"}, {"S": "testing"}]}}

    def test_to_dynamo_nested_dict(self) -> None:
        """Test nested dictionary with floats."""
        data = {"user": {"name": "Alice", "score": 95.5}}
        result = self.serializer.to_dynamo(data)
        expected = {"user": {"M": {"name": {"S": "Alice"}, "score": {"N": "95.5"}}}}
        assert result == expected

    def test_to_dynamo_empty_values(self) -> None:
        """Test empty string and empty list."""
        data = {"name": "", "tags": []}
        result = self.serializer.to_dynamo(data)
        assert result == {"name": {"S": ""}, "tags": {"L": []}}

    def test_to_dynamo_none_values(self) -> None:
        """Test None values are preserved."""
        data = {"optional": None}
        result = self.serializer.to_dynamo(data)
        assert result == {"optional": {"NULL": True}}


@pytest.mark.unit
class TestDynamoSerializerToDynamoValue:
    """Test single value serialization."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_to_dynamo_value_scalar(self) -> None:
        """Test single value serialization."""
        result = self.serializer.to_dynamo_value("test")
        assert result == {"S": "test"}

    def test_to_dynamo_value_float_to_decimal(self) -> None:
        """Test float conversion in single value."""
        result = self.serializer.to_dynamo_value(95.5)
        assert result == {"N": "95.5"}


@pytest.mark.unit
class TestDynamoSerializerFromDynamo:
    """Test deserialization from DynamoDB format to Python."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_from_dynamo_string(self) -> None:
        """Test string deserialization."""
        item: dict[str, Any] = {"name": {"S": "Alice"}}
        result = self.serializer.from_dynamo(item)
        assert result == {"name": "Alice"}

    def test_from_dynamo_number_int(self) -> None:
        """Test integer number deserialization."""
        item: dict[str, Any] = {"age": {"N": "25"}}
        result = self.serializer.from_dynamo(item)
        assert result == {"age": 25}
        assert isinstance(result["age"], int)

    def test_from_dynamo_number_float(self) -> None:
        """Test float number deserialization."""
        item: dict[str, Any] = {"score": {"N": "95.5"}}
        result = self.serializer.from_dynamo(item)
        assert result == {"score": 95.5}
        assert isinstance(result["score"], float)

    def test_from_dynamo_boolean(self) -> None:
        """Test boolean deserialization."""
        item: dict[str, Any] = {"active": {"BOOL": True}}
        result = self.serializer.from_dynamo(item)
        assert result == {"active": True}

    def test_from_dynamo_list(self) -> None:
        """Test list deserialization."""
        item: dict[str, Any] = {"tags": {"L": [{"S": "python"}, {"S": "testing"}]}}
        result = self.serializer.from_dynamo(item)
        assert result == {"tags": ["python", "testing"]}

    def test_from_dynamo_nested(self) -> None:
        """Test nested structure deserialization."""
        item: dict[str, Any] = {"user": {"M": {"name": {"S": "Alice"}, "score": {"N": "95.5"}}}}
        result = self.serializer.from_dynamo(item)
        assert result == {"user": {"name": "Alice", "score": 95.5}}
        assert isinstance(result["user"]["score"], float)

    def test_from_dynamo_empty_list(self) -> None:
        """Test empty list deserialization."""
        item: dict[str, Any] = {"tags": {"L": []}}
        result = self.serializer.from_dynamo(item)
        assert result == {"tags": []}


@pytest.mark.unit
class TestDynamoSerializerFloatPrecision:
    """Test float precision preservation during serialization roundtrip."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_float_precision_preserved(self) -> None:
        """Test that float precision is preserved through serialize/deserialize."""
        original_data = {"score": 95.123456789}
        dynamo_data = self.serializer.to_dynamo(original_data)
        result = self.serializer.from_dynamo(dynamo_data)

        assert result["score"] == 95.123456789
        assert isinstance(result["score"], float)

    def test_integer_floats_become_ints(self) -> None:
        """Test that floats like 10.0 become integers."""
        original_data = {"score": 10.0}
        dynamo_data = self.serializer.to_dynamo(original_data)
        result = self.serializer.from_dynamo(dynamo_data)

        assert result["score"] == 10
        assert isinstance(result["score"], int)

    def test_large_float_precision(self) -> None:
        """Test large float precision."""
        large_float = 123456789.123456789
        original_data = {"value": large_float}
        dynamo_data = self.serializer.to_dynamo(original_data)
        result = self.serializer.from_dynamo(dynamo_data)

        assert result["value"] == large_float
        assert isinstance(result["value"], float)


@pytest.mark.unit
class TestDynamoSerializerComplexTypes:
    """Test complex nested structures."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_complex_nested_structure(self) -> None:
        """Test deeply nested structure with mixed types."""
        complex_data = {
            "user": {
                "profile": {
                    "name": "Alice",
                    "age": 25,
                    "scores": [95.5, 87.2, 92.1],
                    "active": True,
                    "metadata": {
                        "tags": ["premium", "verified"],
                        "last_login": "2023-01-01T10:00:00Z",
                    },
                }
            }
        }

        dynamo_data = self.serializer.to_dynamo(complex_data)
        result = self.serializer.from_dynamo(dynamo_data)

        assert result == complex_data
        assert isinstance(result["user"]["profile"]["age"], int)
        assert isinstance(result["user"]["profile"]["scores"][0], float)
        assert isinstance(result["user"]["profile"]["active"], bool)


@pytest.mark.unit
class TestDynamoSerializerSetHandling:
    """Test set serialization and deserialization."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_set_to_set_conversion(self) -> None:
        """Test that sets are converted to native DynamoDB Sets (SS)."""
        data = {"tags": {"python", "testing", "dynamodb"}}
        result = self.serializer.to_dynamo(data)

        assert "tags" in result
        assert "SS" in result["tags"]
        # SS is a list of strings
        assert set(result["tags"]["SS"]) == {"python", "testing", "dynamodb"}

    def test_frozenset_to_set_conversion(self) -> None:
        """Test that frozensets are converted to native DynamoDB Sets (SS)."""
        data = {"permissions": frozenset(["read", "write"])}
        result = self.serializer.to_dynamo(data)

        assert "permissions" in result
        assert "SS" in result["permissions"]
        assert set(result["permissions"]["SS"]) == {"read", "write"}

    def test_empty_set_filtered_out(self) -> None:
        """Test that empty sets are filtered out (not allowed in DynamoDB)."""
        data: dict[str, Any] = {"tags": set(), "active": True}
        result = self.serializer.to_dynamo(data)

        # 'tags' should be missing
        assert "tags" not in result
        assert result == {"active": {"BOOL": True}}

    def test_nested_set_in_dict(self) -> None:
        """Test sets inside nested dictionaries."""
        data = {"user": {"roles": {"admin", "user"}}}
        result = self.serializer.to_dynamo(data)

        assert "user" in result
        assert "M" in result["user"]
        assert "roles" in result["user"]["M"]
        assert "SS" in result["user"]["M"]["roles"]
        assert set(result["user"]["M"]["roles"]["SS"]) == {"admin", "user"}

    def test_set_in_list(self) -> None:
        """Test sets inside lists."""
        data = {"groups": [{"name": "admins", "perms": {"read", "write"}}]}
        result = self.serializer.to_dynamo(data)

        assert "groups" in result
        assert "L" in result["groups"]
        group = result["groups"]["L"][0]["M"]
        assert "perms" in group
        assert "SS" in group["perms"]
        assert set(group["perms"]["SS"]) == {"read", "write"}


@pytest.mark.unit
class TestDynamoSerializerComplexPythonTypes:
    """Test serialization of complex Python types that Pydantic handles."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_datetime_serialization(self) -> None:
        """Test datetime is serialized as ISO string (handled by Pydantic)."""
        # Note: Pydantic's model_dump converts datetime to string
        # We test the serializer with the already-converted string
        data = {"created_at": "2023-01-01T10:00:00+00:00"}
        result = self.serializer.to_dynamo(data)
        assert result == {"created_at": {"S": "2023-01-01T10:00:00+00:00"}}

    def test_date_serialization(self) -> None:
        """Test date is serialized as ISO string."""
        data = {"birth_date": "2023-01-01"}
        result = self.serializer.to_dynamo(data)
        assert result == {"birth_date": {"S": "2023-01-01"}}

    def test_uuid_serialization(self) -> None:
        """Test UUID is serialized as string."""
        data = {"id": "550e8400-e29b-41d4-a716-446655440000"}
        result = self.serializer.to_dynamo(data)
        assert result == {"id": {"S": "550e8400-e29b-41d4-a716-446655440000"}}

    def test_enum_value_serialization(self) -> None:
        """Test enum values are serialized as their values."""
        data = {"status": "active"}  # Pydantic converts Enum to value
        result = self.serializer.to_dynamo(data)
        assert result == {"status": {"S": "active"}}

    def test_bytes_serialization(self) -> None:
        """Test bytes are serialized as Base64 strings (handled by Pydantic)."""
        # Pydantic converts bytes to base64 string
        data = {"data": "SGVsbG8gV29ybGQ="}  # "Hello World" in base64
        result = self.serializer.to_dynamo(data)
        assert result == {"data": {"S": "SGVsbG8gV29ybGQ="}}

    def test_decimal_serialization(self) -> None:
        """Test Decimal is serialized as string (handled by Pydantic)."""
        # Pydantic converts Decimal to string
        data = {"price": "99.99"}
        result = self.serializer.to_dynamo(data)
        assert result == {"price": {"S": "99.99"}}


@pytest.mark.unit
class TestDynamoSerializerErrors:
    """Test error handling during serialization."""

    def setup_method(self) -> None:
        """Create a fresh serializer for each test."""
        self.serializer = DynamoSerializer()

    def test_unsupported_type_top_level(self) -> None:
        """Test that unsupported types raise DynamoSerializationError."""

        class CustomObj:
            pass

        data = {"obj": CustomObj()}

        with pytest.raises(DynamoSerializationError) as exc_info:
            self.serializer.to_dynamo(data)

        error = exc_info.value
        assert "Failed to serialize field 'obj'" in str(error)
        assert isinstance(error.original_error, TypeError)

    def test_unsupported_type_nested(self) -> None:
        """Test that unsupported nested types raise DynamoSerializationError."""

        class CustomObj:
            pass

        data = {"wrapper": {"obj": CustomObj()}}

        with pytest.raises(DynamoSerializationError) as exc_info:
            self.serializer.to_dynamo(data)

        # Depending on how the serializer traverses, detailed error might vary slightly
        # but it should definitely be a DynamoSerializationError
        error = exc_info.value
        assert "Failed to serialize field 'wrapper'" in str(error)

    def test_unsupported_scalar_value(self) -> None:
        """Test that unsupported scalar values raise DynamoSerializationError."""

        class CustomObj:
            pass

        with pytest.raises(DynamoSerializationError) as exc_info:
            self.serializer.to_dynamo_value(CustomObj())

        assert "Failed to serialize value" in str(exc_info.value)
