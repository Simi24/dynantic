from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from botocore.exceptions import ClientError


class DynanticError(Exception):
    """Base exception for all Dynantic errors."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class TableNotFoundError(DynanticError):
    """Raised when the DynamoDB table does not exist."""

    def __init__(self, table_name: str, original_error: Exception | None = None) -> None:
        super().__init__(f"Table '{table_name}' not found", original_error)
        self.table_name = table_name


class ItemNotFoundError(DynanticError):
    """Raised when an item is not found (for future use with strict gets)."""

    def __init__(self, key: dict[str, Any], original_error: Exception | None = None) -> None:
        super().__init__(f"Item with key {key} not found", original_error)
        self.key = key


class ConditionalCheckFailedError(DynanticError):
    """Raised when a conditional write fails."""

    def __init__(
        self, condition: str | None = None, original_error: Exception | None = None
    ) -> None:
        msg = "Conditional check failed"
        if condition:
            msg += f": {condition}"
        super().__init__(msg, original_error)
        self.condition = condition


class ProvisionedThroughputExceededError(DynanticError):
    """Raised when DynamoDB throttles requests."""

    def __init__(
        self, message: str = "Request rate exceeded", original_error: Exception | None = None
    ) -> None:
        super().__init__(message, original_error)


class ItemCollectionSizeLimitError(DynanticError):
    """Raised when item collection size exceeds 10GB limit."""

    def __init__(
        self,
        message: str = "Item collection size limit exceeded",
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, original_error)


class TransactionConflictError(DynanticError):
    """Raised when a transaction conflicts with another ongoing transaction."""

    def __init__(
        self, message: str = "Transaction conflict", original_error: Exception | None = None
    ) -> None:
        super().__init__(message, original_error)


class RequestTimeoutError(DynanticError):
    """Raised when a request to DynamoDB times out."""

    def __init__(
        self, message: str = "Request timed out", original_error: Exception | None = None
    ) -> None:
        super().__init__(message, original_error)


class ValidationError(DynanticError):
    """Raised for data validation errors from DynamoDB."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, original_error)
        self.field = field
        self.value = value


@contextmanager
def handle_dynamo_errors(table_name: str | None = None) -> Generator[None, None, None]:
    """
    Context manager that catches botocore.exceptions.ClientError
    and raises the appropriate DynanticError subclass.

    Args:
        table_name: Optional table name for better error messages

    Usage:
        with handle_dynamo_errors(table_name="users"):
            client.get_item(...)
    """
    try:
        yield
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Handle specific error types
        if error_code == "ResourceNotFoundException":
            raise TableNotFoundError(table_name=table_name or "unknown", original_error=e) from e

        if error_code == "ConditionalCheckFailedException":
            raise ConditionalCheckFailedError(original_error=e) from e

        if error_code in (
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
            "RequestLimitExceeded",
        ):
            raise ProvisionedThroughputExceededError(message=error_message, original_error=e) from e

        if error_code in ("ValidationException", "SerializationException"):
            raise ValidationError(message=error_message, original_error=e) from e

        if error_code == "ItemCollectionSizeLimitExceededException":
            raise ItemCollectionSizeLimitError(message=error_message, original_error=e) from e

        if error_code == "TransactionConflictException":
            raise TransactionConflictError(message=error_message, original_error=e) from e

        if error_code in ("RequestTimeout", "RequestTimeoutException"):
            raise RequestTimeoutError(message=error_message, original_error=e) from e

        # Unknown error: wrap in generic DynanticError
        raise DynanticError(
            message=f"DynamoDB error ({error_code}): {error_message}", original_error=e
        ) from e


class DynamoSerializationError(DynanticError):
    """Raised when serialization to DynamoDB format fails (e.g. unsupported type)."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message, original_error)
