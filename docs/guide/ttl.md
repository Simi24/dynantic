# TTL (Time To Live)

Automatic datetime-to-epoch conversion for DynamoDB TTL attributes.

## datetime TTL (Recommended)

```python
from datetime import datetime, timedelta, timezone
from dynantic import DynamoModel, Key, TTL

class Session(DynamoModel):
    session_id: str = Key()
    user_id: str
    expires_at: datetime = TTL()  # Stored as epoch seconds in DynamoDB

    class Meta:
        table_name = "sessions"

# Create with datetime — automatically converted to epoch on save
session = Session(
    session_id="sess-123",
    user_id="user-42",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
)
session.save()

# Read back — automatically converted from epoch to datetime
retrieved = Session.get("sess-123")
print(isinstance(retrieved.expires_at, datetime))  # True
```

## int TTL (Raw Epoch)

```python
import time
from dynantic import DynamoModel, Key, TTL

class CacheEntry(DynamoModel):
    cache_key: str = Key()
    value: str
    ttl: int = TTL()

    class Meta:
        table_name = "cache"

entry = CacheEntry(
    cache_key="api:/users/42",
    value='{"name": "John"}',
    ttl=int(time.time()) + 3600,  # Expires in 1 hour
)
entry.save()
```

## Works with All Write Paths

TTL serialization is handled automatically across all write operations:

- `save()`
- `batch_save()`
- `batch_writer()`
- `transact_save()`
- `transact_write()`

!!! warning "Table-level TTL setup required"
    TTL must also be enabled on the DynamoDB table itself. Dynantic only handles the field serialization.

    ```hcl
    # Terraform example
    resource "aws_dynamodb_table" "sessions" {
      # ...
      ttl {
        attribute_name = "expires_at"
        enabled        = true
      }
    }
    ```
