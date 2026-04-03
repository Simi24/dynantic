# Configuration

## AWS Credentials

Dynantic uses boto3, so it follows the standard AWS credential resolution:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. Shared credentials file (`~/.aws/credentials`)
3. AWS config file (`~/.aws/config`)
4. IAM role (EC2, Lambda, ECS)

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

## Client Lifecycle

### Global Singleton (Lambda, Scripts)

```python
import boto3
from dynantic import DynamoModel

# Create once at module level
client = boto3.client("dynamodb")
DynamoModel.set_client(client)
```

### Per-Request Clients (Multi-Tenant)

```python
from dynantic import DynamoModel

with User.using_client(tenant_specific_client):
    user = User.get("user-123")
```

## Retry Configuration

```python
from botocore.config import Config
import boto3

config = Config(
    retries={
        "max_attempts": 10,   # Default: 3
        "mode": "adaptive"    # or "standard", "legacy"
    },
    connect_timeout=5,
    read_timeout=10
)

client = boto3.client("dynamodb", config=config)
DynamoModel.set_client(client)
```

**Retry modes:**

| Mode | Description |
|---|---|
| `standard` | Fixed delays with exponential backoff |
| `adaptive` | Adjusts retry rate based on throttling |
| `legacy` | Old boto behavior (not recommended) |

## Connection Pooling

```python
config = Config(max_pool_connections=50)  # Default: 10
client = boto3.client("dynamodb", config=config)
```

## Testing with Mocks

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_dynamo_client():
    client = MagicMock()
    client.get_item.return_value = {
        "Item": {
            "user_id": {"S": "test-123"},
            "email": {"S": "test@example.com"}
        }
    }
    return client

def test_user_get(mock_dynamo_client):
    User.set_client(mock_dynamo_client)
    user = User.get("test-123")
    assert user.user_id == "test-123"
    mock_dynamo_client.get_item.assert_called_once()
```

## Security

### Pagination Cursors

Cursors are unencrypted dicts — always re-apply authorization server-side:

```python
# Always filter by authenticated user
@app.get("/orders")
def get_orders(current_user: User, cursor: dict | None = None):
    return Order.query(current_user.user_id).page(start_key=cursor)
```

### Conditional Expressions

Never pass raw user input to `Attr()`:

```python
# Bad
condition = Attr(request.query_params["field"]).exists()

# Good — use model fields
condition = User.email.exists()
```

### IAM Minimum Permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem"
  ],
  "Resource": [
    "arn:aws:dynamodb:*:*:table/your-table",
    "arn:aws:dynamodb:*:*:table/your-table/index/*"
  ]
}
```
