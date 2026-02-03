"""
Shared pytest fixtures and configuration for Dynantic tests.

This module provides common fixtures used across unit and integration tests,
including mocked boto3 clients, LocalStack clients, and test model definitions.
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import boto3
import pytest

from dynantic import DynamoModel, Key, SortKey

if TYPE_CHECKING:
    from tests.helpers.localstack import LocalStackHelper


class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Integration tests against LocalStack")
    config.addinivalue_line("markers", "slow: Slow tests that may take longer")


@pytest.fixture(scope="session")
def localstack_endpoint() -> str:
    """Get LocalStack endpoint URL from environment or default."""
    return os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


@pytest.fixture(scope="session")
def localstack_client(localstack_endpoint: str):
    """
    Creates a boto3 client connected to LocalStack.

    This fixture is session-scoped to avoid creating multiple clients.
    """
    return boto3.client(
        "dynamodb",
        endpoint_url=localstack_endpoint,
        region_name="eu-south-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture
def mock_client():
    """
    Creates a fully mocked boto3 DynamoDB client.

    This fixture provides a mock client for unit tests that don't need
    real DynamoDB interactions.
    """
    client = MagicMock()
    client.get_paginator.return_value = MagicMock()
    return client


@pytest.fixture
def sample_user_model():
    """
    Returns a User model class for testing.

    This model has only a partition key (email).
    """

    class User(DynamoModel):
        class Meta:
            table_name = "test_users"

        email: str = Key()
        username: str
        age: int
        score: float = 0.0
        tags: list[str] = []
        active: bool = True

    return User


@pytest.fixture
def sample_message_model():
    """
    Returns a Message model class for testing.

    This model has both partition key (room_id) and sort key (timestamp).
    """

    class Message(DynamoModel):
        class Meta:
            table_name = "test_messages"

        room_id: str = Key()
        timestamp: str = SortKey()
        content: str
        user: str
        likes: int = 0

    return Message


@pytest.fixture
def clean_table(localstack_client, request):
    """
    Creates a fresh DynamoDB table for each test and cleans up after.

    This fixture automatically creates a table with the specified schema
    and deletes all items after the test completes.

    Usage:
        @pytest.mark.parametrize("table_name,pk_name,sk_name", [
            ("test_users", "email", None),
            ("test_messages", "room_id", "timestamp"),
        ])
        def test_something(clean_table):
            # Table is created and cleaned automatically
            pass
    """
    # Get table parameters from the test
    table_name = getattr(request, "param", {}).get("table_name", "test_table")
    pk_name = getattr(request, "param", {}).get("pk_name", "pk")
    sk_name = getattr(request, "param", {}).get("sk_name", None)

    # Create table
    key_schema = [{"AttributeName": pk_name, "KeyType": "HASH"}]
    attr_defs = [{"AttributeName": pk_name, "AttributeType": "S"}]

    if sk_name:
        key_schema.append({"AttributeName": sk_name, "KeyType": "RANGE"})
        attr_defs.append({"AttributeName": sk_name, "AttributeType": "S"})

    try:
        localstack_client.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attr_defs,
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
    except localstack_client.exceptions.ResourceInUseException:
        # Table already exists, delete all items
        pass

    # Wait for table to be active
    localstack_client.get_waiter("table_exists").wait(TableName=table_name)

    # Clean up any existing items
    _delete_all_items(localstack_client, table_name, pk_name, sk_name)

    yield table_name

    # Cleanup: delete all items after test
    _delete_all_items(localstack_client, table_name, pk_name, sk_name)


def _delete_all_items(client, table_name: str, pk_name: str, sk_name: str | None):
    """Helper to delete all items from a table."""
    try:
        paginator = client.get_paginator("scan")
        for page in paginator.paginate(TableName=table_name):
            for item in page["Items"]:
                key = {pk_name: item[pk_name]}
                if sk_name and sk_name in item:
                    key[sk_name] = item[sk_name]
                client.delete_item(TableName=table_name, Key=key)
    except Exception:
        # Ignore errors during cleanup
        pass


@pytest.fixture
def inject_mock_client(mock_client, sample_user_model, sample_message_model):
    """
    Injects a mock client into the test models.

    This fixture sets the mock client on both sample models so they
    use the mock instead of trying to connect to real DynamoDB.
    """
    sample_user_model.set_client(mock_client)
    sample_message_model.set_client(mock_client)
    return mock_client


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "age": 25,
        "score": 95.5,
        "tags": ["python", "testing"],
        "active": True,
    }


@pytest.fixture
def sample_message_data() -> dict[str, Any]:
    """Sample message data for testing."""
    return {
        "room_id": "general",
        "timestamp": "2023-01-01T10:00:00Z",
        "content": "Hello, world!",
        "user": "alice",
        "likes": 5,
    }


@pytest.fixture
def sample_messages_data() -> list[dict[str, Any]]:
    """Multiple sample messages for testing queries."""
    return [
        {
            "room_id": "general",
            "timestamp": "2023-01-01T09:00:00Z",
            "content": "Good morning!",
            "user": "alice",
            "likes": 2,
        },
        {
            "room_id": "general",
            "timestamp": "2023-01-01T10:00:00Z",
            "content": "Hello, world!",
            "user": "bob",
            "likes": 5,
        },
        {
            "room_id": "general",
            "timestamp": "2023-01-01T11:00:00Z",
            "content": "How is everyone?",
            "user": "charlie",
            "likes": 1,
        },
        {
            "room_id": "python",
            "timestamp": "2023-01-01T10:30:00Z",
            "content": "Check out this library!",
            "user": "diana",
            "likes": 10,
        },
    ]


@pytest.fixture
def mock_serializer():
    """Mock serializer for testing."""
    serializer = MagicMock()
    serializer.to_dynamo_value.return_value = {"S": "mocked_value"}
    return serializer


# Integration Test Fixtures


@pytest.fixture(scope="session")
def localstack_helper(localstack_endpoint: str) -> "LocalStackHelper":
    """Provides a LocalStackHelper instance for integration tests."""
    from tests.helpers.localstack import LocalStackHelper

    return LocalStackHelper(endpoint_url=localstack_endpoint)


@pytest.fixture
def integration_user_model(localstack_client):
    """
    Returns a User model class configured for LocalStack integration tests.

    This model has only a partition key (email) and uses the LocalStack client.
    """
    from dynantic import DynamoModel, Key

    class User(DynamoModel):
        class Meta:
            table_name = "integration_test_users"

        email: str = Key()
        username: str
        age: int
        score: float = 0.0
        tags: list[str] = []
        active: bool = True

    # Set the LocalStack client
    User.set_client(localstack_client)
    return User


@pytest.fixture
def integration_message_model(localstack_client):
    """
    Returns a Message model class configured for LocalStack integration tests.

    This model has both partition key (room_id) and sort key (timestamp).
    """
    from dynantic import DynamoModel, Key, SortKey

    class Message(DynamoModel):
        class Meta:
            table_name = "integration_test_messages"

        room_id: str = Key()
        timestamp: str = SortKey()
        content: str
        user: str
        likes: int = 0

    # Set the LocalStack client
    Message.set_client(localstack_client)
    return Message


@pytest.fixture
def clean_integration_tables(localstack_helper, integration_user_model, integration_message_model):
    """
    Creates fresh tables for integration tests and cleans up after.

    This fixture ensures tables exist and are empty before each test.
    """
    # Create tables
    localstack_helper.create_table(
        table_name=integration_user_model._meta.table_name,
        pk_name=integration_user_model._meta.pk_name,
        pk_type="S",
    )

    localstack_helper.create_table(
        table_name=integration_message_model._meta.table_name,
        pk_name=integration_message_model._meta.pk_name,
        pk_type="S",
        sk_name=integration_message_model._meta.sk_name,
        sk_type="S",
    )

    # Clear any existing data
    localstack_helper.clear_table(
        table_name=integration_user_model._meta.table_name,
        pk_name=integration_user_model._meta.pk_name,
    )

    localstack_helper.clear_table(
        table_name=integration_message_model._meta.table_name,
        pk_name=integration_message_model._meta.pk_name,
        sk_name=integration_message_model._meta.sk_name,
    )

    yield

    # Cleanup after test
    try:
        localstack_helper.clear_table(
            table_name=integration_user_model._meta.table_name,
            pk_name=integration_user_model._meta.pk_name,
        )
        localstack_helper.clear_table(
            table_name=integration_message_model._meta.table_name,
            pk_name=integration_message_model._meta.pk_name,
            sk_name=integration_message_model._meta.sk_name,
        )
    except Exception:
        # Ignore cleanup errors
        pass


# GSI Test Fixtures


@pytest.fixture
def integration_order_model(localstack_client):
    """
    Returns an Order model class with GSIs configured for LocalStack integration tests.

    This model has:
    - Primary key: order_id
    - GSI "customer-index": customer_id (partition key)
    - GSI "status-date-index": status (partition key), order_date (sort key)
    """
    from dynantic import DynamoModel, GSIKey, GSISortKey, Key

    class Order(DynamoModel):
        class Meta:
            table_name = "integration_test_orders"

        order_id: str = Key()
        customer_id: str = GSIKey(index_name="customer-index")
        status: str = GSIKey(index_name="status-date-index")
        order_date: str = GSISortKey(index_name="status-date-index")
        amount: float
        items: list[str] = []

    # Set the LocalStack client
    Order.set_client(localstack_client)
    return Order


@pytest.fixture
def clean_gsi_tables(localstack_helper, integration_order_model):
    """
    Creates fresh tables with GSIs for integration tests and cleans up after.

    This fixture ensures GSI tables exist and are empty before each test.
    """
    # Define GSI configurations
    gsi_definitions = [
        {
            "index_name": "customer-index",
            "pk_name": "customer_id",
            "pk_type": "S",
        },
        {
            "index_name": "status-date-index",
            "pk_name": "status",
            "pk_type": "S",
            "sk_name": "order_date",
            "sk_type": "S",
        },
    ]

    # Create table with GSIs
    localstack_helper.create_table_with_gsi(
        table_name=integration_order_model._meta.table_name,
        pk_name=integration_order_model._meta.pk_name,
        pk_type="S",
        gsi_definitions=gsi_definitions,
    )

    # Clear any existing data
    localstack_helper.clear_table(
        table_name=integration_order_model._meta.table_name,
        pk_name=integration_order_model._meta.pk_name,
    )

    yield

    # Cleanup after test
    try:
        localstack_helper.clear_table(
            table_name=integration_order_model._meta.table_name,
            pk_name=integration_order_model._meta.pk_name,
        )
    except Exception:
        # Ignore cleanup errors
        pass


@pytest.fixture
def sample_order_data() -> dict[str, Any]:
    """Sample order data for GSI testing."""
    return {
        "order_id": "ORD-001",
        "customer_id": "CUST-123",
        "status": "PENDING",
        "order_date": "2023-01-15",
        "amount": 99.99,
        "items": ["item1", "item2"],
    }


@pytest.fixture
def sample_orders_data() -> list[dict[str, Any]]:
    """Multiple sample orders for GSI testing."""
    return [
        {
            "order_id": "ORD-001",
            "customer_id": "CUST-123",
            "status": "PENDING",
            "order_date": "2023-01-15",
            "amount": 99.99,
            "items": ["laptop", "mouse"],
        },
        {
            "order_id": "ORD-002",
            "customer_id": "CUST-123",
            "status": "SHIPPED",
            "order_date": "2023-01-16",
            "amount": 49.99,
            "items": ["book"],
        },
        {
            "order_id": "ORD-003",
            "customer_id": "CUST-456",
            "status": "PENDING",
            "order_date": "2023-01-17",
            "amount": 149.99,
            "items": ["phone", "case"],
        },
        {
            "order_id": "ORD-004",
            "customer_id": "CUST-456",
            "status": "DELIVERED",
            "order_date": "2023-01-18",
            "amount": 29.99,
            "items": ["headphones"],
        },
        {
            "order_id": "ORD-005",
            "customer_id": "CUST-789",
            "status": "PENDING",
            "order_date": "2023-01-19",
            "amount": 79.99,
            "items": ["tablet"],
        },
    ]


# Comprehensive Type Support Fixtures


@pytest.fixture
def comprehensive_user_model(localstack_client):
    """
    Returns a User model class with comprehensive Python types for testing.

    This model includes datetime, UUID, Enum, and set types.
    Float is used for balance - the library handles Decimal conversion for DynamoDB.
    """
    from dynantic import DynamoModel, Key

    class ComprehensiveUser(DynamoModel):
        class Meta:
            table_name = "test_comprehensive_users"

        user_id: str = Key()  # Using str for simplicity in tests
        email: str
        status: UserStatus = UserStatus.PENDING
        created_at: datetime
        balance: float = 0.0  # Float in app, Decimal in DynamoDB
        tags: set[str] = set()  # Will be stored as List in DynamoDB
        permissions: set[str] = set()

    # Set the LocalStack client
    ComprehensiveUser.set_client(localstack_client)
    return ComprehensiveUser


@pytest.fixture
def comprehensive_message_model(localstack_client):
    """
    Returns a Message model class with datetime sort key.

    This model uses datetime for the sort key instead of string.
    """
    from dynantic import DynamoModel, Key, SortKey

    class ComprehensiveMessage(DynamoModel):
        class Meta:
            table_name = "test_comprehensive_messages"

        room_id: str = Key()
        timestamp: datetime = SortKey()  # datetime instead of str!
        content: str
        user: str
        likes: int = 0

    # Set the LocalStack client
    ComprehensiveMessage.set_client(localstack_client)
    return ComprehensiveMessage


@pytest.fixture
def sample_comprehensive_user_data() -> dict[str, Any]:
    """Sample comprehensive user data with all supported types."""
    return {
        "user_id": "user-123",
        "email": "test@example.com",
        "status": UserStatus.ACTIVE,
        "created_at": datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc),
        "balance": 99.99,  # float - library handles Decimal conversion
        "tags": {"premium", "verified"},  # set[str]
        "permissions": {"read", "write"},  # set[str]
    }


@pytest.fixture
def sample_comprehensive_message_data() -> dict[str, Any]:
    """Sample comprehensive message data with datetime."""
    return {
        "room_id": "general",
        "timestamp": datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc),
        "content": "Hello, world!",
        "user": "alice",
        "likes": 5,
    }


@pytest.fixture
def clean_comprehensive_tables(
    localstack_helper, comprehensive_user_model, comprehensive_message_model
):
    """
    Creates fresh tables for comprehensive type tests and cleans up after.

    This fixture ensures tables exist and are empty before each test.
    """
    # Create tables
    localstack_helper.create_table(
        table_name=comprehensive_user_model._meta.table_name,
        pk_name=comprehensive_user_model._meta.pk_name,
        pk_type="S",
    )

    localstack_helper.create_table(
        table_name=comprehensive_message_model._meta.table_name,
        pk_name=comprehensive_message_model._meta.pk_name,
        pk_type="S",
        sk_name=comprehensive_message_model._meta.sk_name,
        sk_type="S",  # DynamoDB stores datetime as ISO string
    )

    # Clear any existing data
    localstack_helper.clear_table(
        table_name=comprehensive_user_model._meta.table_name,
        pk_name=comprehensive_user_model._meta.pk_name,
    )

    localstack_helper.clear_table(
        table_name=comprehensive_message_model._meta.table_name,
        pk_name=comprehensive_message_model._meta.pk_name,
        sk_name=comprehensive_message_model._meta.sk_name,
    )

    yield

    # Cleanup after test
    try:
        localstack_helper.clear_table(
            table_name=comprehensive_user_model._meta.table_name,
            pk_name=comprehensive_user_model._meta.pk_name,
        )
        localstack_helper.clear_table(
            table_name=comprehensive_message_model._meta.table_name,
            pk_name=comprehensive_message_model._meta.pk_name,
            sk_name=comprehensive_message_model._meta.sk_name,
        )
    except Exception:
        # Ignore cleanup errors
        pass
