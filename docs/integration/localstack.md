# LocalStack Testing

Run integration tests against a local DynamoDB using LocalStack.

## docker-compose.yaml

```yaml
version: '3.8'
services:
  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=dynamodb
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
    volumes:
      - "/tmp/localstack:/tmp/localstack"
```

```bash
docker compose up -d
```

## Configure Dynantic Client

```python
import boto3
from dynantic import DynamoModel

client = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
DynamoModel.set_client(client)
```

## Pytest Setup

```python
import boto3
import pytest
import os

@pytest.fixture(scope="session", autouse=True)
def localstack_setup():
    os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def dynamo_client():
    return boto3.client("dynamodb", endpoint_url="http://localhost:4566")

@pytest.fixture
def create_test_table(dynamo_client):
    dynamo_client.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "email", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    yield
    dynamo_client.delete_table(TableName="users")
```

## CI with GitHub Actions

The CI workflow runs integration tests against LocalStack as a service container:

```yaml
services:
  localstack:
    image: localstack/localstack:3.0
    ports:
      - 4566:4566
    env:
      SERVICES: dynamodb
    options: >-
      --health-cmd "curl http://localhost:4566/_localstack/health"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

!!! tip "Health check"
    Always wait for LocalStack to be ready before running tests:
    ```bash
    timeout 120 bash -c 'until curl -f http://localhost:4566/_localstack/health; do sleep 5; done'
    ```
