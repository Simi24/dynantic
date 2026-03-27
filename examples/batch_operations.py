"""
Batch Operations Example

Demonstrates Dynantic's batch API:
- batch_save: Write multiple items (auto-chunked at 25)
- batch_get: Read multiple items by key (auto-chunked at 100)
- batch_delete: Delete multiple items by key (auto-chunked at 25)
- batch_writer: Context manager for mixed put/delete with auto-flush
"""

from dynantic import DynamoModel, Key


class User(DynamoModel):
    user_id: str = Key()
    name: str
    email: str
    age: int

    class Meta:
        table_name = "users"


# ── batch_save ───────────────────────────────────────────────────────

# Save 50 users in one call (auto-chunks into 2 batches of 25)
users = [
    User(user_id=f"u{i}", name=f"User {i}", email=f"user{i}@example.com", age=20 + i)
    for i in range(50)
]
User.batch_save(users)
print(f"Saved {len(users)} users")


# ── batch_get ────────────────────────────────────────────────────────

# Fetch multiple users by key (auto-chunks into groups of 100)
keys = [{"user_id": f"u{i}"} for i in range(50)]
fetched_users = User.batch_get(keys)
print(f"Fetched {len(fetched_users)} users")

# NOTE: DynamoDB does not guarantee order in batch_get responses.
# If you need ordered results, sort them after fetching:
sorted_users = sorted(fetched_users, key=lambda u: u.user_id)


# ── batch_delete ─────────────────────────────────────────────────────

# Delete a subset of users (auto-chunks at 25)
keys_to_delete = [{"user_id": f"u{i}"} for i in range(25)]
User.batch_delete(keys_to_delete)
print(f"Deleted {len(keys_to_delete)} users")


# ── batch_writer (context manager) ──────────────────────────────────

# Mix saves and deletes in a single batch context.
# Auto-flushes every 25 items and on exit.
with User.batch_writer() as batch:
    # Add new users
    for i in range(100, 110):
        batch.save(
            User(user_id=f"u{i}", name=f"User {i}", email=f"user{i}@example.com", age=25)
        )

    # Delete some existing users
    for i in range(25, 30):
        batch.delete(user_id=f"u{i}")

print("Batch writer: saved 10, deleted 5")


# ── Exponential backoff ─────────────────────────────────────────────

# All batch operations automatically retry unprocessed items with
# exponential backoff (up to 5 retries). This handles DynamoDB
# throttling transparently — no manual retry logic needed.
