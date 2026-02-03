"""
Unit tests for custom exception handling in Dynantic.

These tests verify that the exception hierarchy works correctly and that
the handle_dynamo_errors context manager properly translates botocore
ClientError exceptions into DynanticError subclasses.
"""

import pytest
from botocore.exceptions import ClientError

from dynantic.exceptions import (
    ConditionalCheckFailedError,
    DynamoSerializationError,
    DynanticError,
    ItemNotFoundError,
    ProvisionedThroughputExceededError,
    TableNotFoundError,
    ValidationError,
    handle_dynamo_errors,
)


class TestExceptionHierarchy:
    """Test the exception class hierarchy and instantiation."""

    def test_dynantic_error_base_class(self):
        """Test that DynanticError is the base exception class."""
        error = DynanticError("Test message")
        assert isinstance(error, Exception)
        assert error.message == "Test message"
        assert error.original_error is None

    def test_dynantic_error_with_original_error(self):
        """Test DynanticError with original error preservation."""
        original = ValueError("Original error")
        error = DynanticError("Wrapped message", original_error=original)
        assert error.message == "Wrapped message"
        assert error.original_error is original

    def test_table_not_found_error(self):
        """Test TableNotFoundError instantiation."""
        error = TableNotFoundError("test_table")
        assert isinstance(error, DynanticError)
        assert error.table_name == "test_table"
        assert "test_table" in str(error)

    def test_item_not_found_error(self):
        """Test ItemNotFoundError instantiation."""
        key = {"pk": "test", "sk": "item"}
        error = ItemNotFoundError(key)
        assert isinstance(error, DynanticError)
        assert error.key == key
        assert "test" in str(error)

    def test_conditional_check_failed_error(self):
        """Test ConditionalCheckFailedError instantiation."""
        error = ConditionalCheckFailedError("attribute_not_exists(pk)")
        assert isinstance(error, DynanticError)
        assert error.condition == "attribute_not_exists(pk)"

    def test_provisioned_throughput_exceeded_error(self):
        """Test ProvisionedThroughputExceededError instantiation."""
        error = ProvisionedThroughputExceededError("Rate exceeded")
        assert isinstance(error, DynanticError)
        assert "Rate exceeded" in str(error)

    def test_validation_error(self):
        """Test ValidationError instantiation."""
        error = ValidationError("Invalid value", field="age", value=-5)
        assert isinstance(error, DynanticError)
        assert error.field == "age"
        assert error.field == "age"
        assert error.value == -5

    def test_dynamo_serialization_error(self):
        """Test DynamoSerializationError instantiation."""
        error = DynamoSerializationError("Serialization failed")
        assert isinstance(error, DynanticError)
        assert "Serialization failed" in str(error)


class TestHandleDynamoErrors:
    """Test the handle_dynamo_errors context manager."""

    def test_successful_operation(self):
        """Test that successful operations pass through normally."""
        with handle_dynamo_errors():
            result = 42
        assert result == 42

    def test_resource_not_found_exception(self):
        """Test ResourceNotFoundException mapping to TableNotFoundError."""
        mock_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Requested resource not found",
                }
            },
            operation_name="GetItem",
        )

        with pytest.raises(TableNotFoundError) as exc_info:
            with handle_dynamo_errors(table_name="users"):
                raise mock_error

        error = exc_info.value
        assert error.table_name == "users"
        assert error.original_error is mock_error
        assert isinstance(error, DynanticError)

    def test_conditional_check_failed_exception(self):
        """Test ConditionalCheckFailedException mapping."""
        mock_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "The conditional request failed",
                }
            },
            operation_name="PutItem",
        )

        with pytest.raises(ConditionalCheckFailedError) as exc_info:
            with handle_dynamo_errors():
                raise mock_error

        error = exc_info.value
        assert error.original_error is mock_error
        assert isinstance(error, DynanticError)

    def test_throttling_exceptions(self):
        """Test various throttling exception codes."""
        throttling_codes = [
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
            "RequestLimitExceeded",
        ]

        for code in throttling_codes:
            mock_error = ClientError(
                error_response={"Error": {"Code": code, "Message": "Rate limit exceeded"}},
                operation_name="GetItem",
            )

            with pytest.raises(ProvisionedThroughputExceededError) as exc_info:
                with handle_dynamo_errors():
                    raise mock_error

            error = exc_info.value
            assert error.original_error is mock_error
            assert isinstance(error, DynanticError)

    def test_validation_exceptions(self):
        """Test validation-related exception codes."""
        validation_codes = ["ValidationException", "SerializationException"]

        for code in validation_codes:
            mock_error = ClientError(
                error_response={"Error": {"Code": code, "Message": "Validation failed"}},
                operation_name="PutItem",
            )

            with pytest.raises(ValidationError) as exc_info:
                with handle_dynamo_errors():
                    raise mock_error

            error = exc_info.value
            assert error.original_error is mock_error
            assert isinstance(error, DynanticError)

    def test_unknown_error_code(self):
        """Test unknown error codes map to generic DynanticError."""
        mock_error = ClientError(
            error_response={
                "Error": {"Code": "UnknownErrorCode", "Message": "Something unexpected happened"}
            },
            operation_name="Scan",
        )

        with pytest.raises(DynanticError) as exc_info:
            with handle_dynamo_errors():
                raise mock_error

        error = exc_info.value
        assert "UnknownErrorCode" in str(error)
        assert "Something unexpected happened" in str(error)
        assert error.original_error is mock_error
        assert isinstance(error, DynanticError)

    def test_error_without_table_name(self):
        """Test error handling when no table name is provided."""
        mock_error = ClientError(
            error_response={
                "Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}
            },
            operation_name="GetItem",
        )

        with pytest.raises(TableNotFoundError) as exc_info:
            with handle_dynamo_errors():
                raise mock_error

        error = exc_info.value
        assert error.table_name == "unknown"

    def test_error_chaining(self):
        """Test that original exceptions are properly chained."""
        original_error = ValueError("Original cause")
        mock_client_error = ClientError(
            error_response={"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
            operation_name="PutItem",
        )

        with pytest.raises(ValidationError) as exc_info:
            with handle_dynamo_errors():
                raise mock_client_error

        dynantic_error = exc_info.value
        assert dynantic_error.original_error is mock_client_error

        # Test that the exception chaining works (from clause)
        with pytest.raises(ValidationError) as chained_exc:
            try:
                raise mock_client_error
            except ClientError:
                raise ValidationError(
                    "Wrapped", original_error=mock_client_error
                ) from mock_client_error

        assert chained_exc.value.__cause__ is mock_client_error

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from DynanticError."""
        exceptions = [
            TableNotFoundError("test"),
            ItemNotFoundError({"pk": "test"}),
            ConditionalCheckFailedError(),
            ProvisionedThroughputExceededError(),
            ProvisionedThroughputExceededError(),
            ValidationError("test"),
            DynamoSerializationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, DynanticError)
            assert isinstance(exc, Exception)
