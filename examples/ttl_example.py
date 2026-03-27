"""
TTL (Time To Live) Example

Demonstrates how Dynantic handles automatic TTL serialization:
- datetime fields are converted to epoch seconds on save
- epoch seconds are converted back to datetime on read
- int TTL fields pass through unchanged
"""

import time
from datetime import datetime, timedelta, timezone

from dynantic import TTL, DynamoModel, Key

# ── datetime TTL (recommended) ──────────────────────────────────────


class Session(DynamoModel):
    """User session with automatic expiry."""

    session_id: str = Key()
    user_id: str
    expires_at: datetime = TTL()

    class Meta:
        table_name = "sessions"


# Create a session that expires in 24 hours
session = Session(
    session_id="sess-abc123",
    user_id="user-42",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
)
session.save()
# DynamoDB stores expires_at as N (epoch seconds): {"N": "1750000000"}

# Read it back — automatically deserialized to datetime
retrieved = Session.get("sess-abc123")
if retrieved:
    print(f"Session expires at: {retrieved.expires_at}")
    print(f"Is datetime: {isinstance(retrieved.expires_at, datetime)}")  # True


# ── int TTL (raw epoch seconds) ─────────────────────────────────────


class CacheEntry(DynamoModel):
    """Cache entry with raw epoch TTL."""

    cache_key: str = Key()
    value: str
    ttl: int = TTL()

    class Meta:
        table_name = "cache"


# Store with explicit epoch
entry = CacheEntry(
    cache_key="api:/users/42",
    value='{"name": "John"}',
    ttl=int(time.time()) + 3600,  # Expires in 1 hour
)
entry.save()


# ── TTL works with all write paths ──────────────────────────────────

# Batch save
sessions = [
    Session(
        session_id=f"sess-{i}",
        user_id=f"user-{i}",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    for i in range(10)
]
Session.batch_save(sessions)

# Batch writer
with Session.batch_writer() as batch:
    batch.save(
        Session(
            session_id="sess-bw",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )

# Transactions
DynamoModel.transact_save(
    [
        Session(
            session_id="sess-tx",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
    ]
)

print("\nAll write paths handle TTL serialization automatically.")

# NOTE: TTL must also be enabled on the DynamoDB table itself.
# With Terraform:
#   resource "aws_dynamodb_table" "sessions" {
#     ...
#     ttl {
#       attribute_name = "expires_at"
#       enabled        = true
#     }
#   }
