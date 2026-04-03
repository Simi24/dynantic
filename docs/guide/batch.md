# Batch Operations

Read and write items in bulk with automatic chunking and exponential backoff retry.

## Batch Save

Save up to thousands of items — auto-chunked into groups of 25.

```python
users = [
    User(user_id=f"u{i}", name=f"User {i}", email=f"user{i}@example.com", age=20 + i)
    for i in range(50)
]
User.batch_save(users)
```

## Batch Get

Fetch multiple items by key — auto-chunked into groups of 100.

```python
keys = [{"user_id": f"u{i}"} for i in range(50)]
users = User.batch_get(keys)
```

!!! warning "Order not guaranteed"
    DynamoDB does not guarantee order in `batch_get` responses. Sort results after fetching if needed:
    ```python
    sorted_users = sorted(users, key=lambda u: u.user_id)
    ```

## Batch Delete

Delete multiple items by key — auto-chunked into groups of 25.

```python
User.batch_delete([{"user_id": f"u{i}"} for i in range(50)])
```

## Batch Writer (Context Manager)

Mix saves and deletes in a single batch context. Auto-flushes every 25 items and on exit.

```python
with User.batch_writer() as batch:
    # Add new users
    for i in range(100, 110):
        batch.save(
            User(user_id=f"u{i}", name=f"User {i}", email=f"user{i}@example.com", age=25)
        )

    # Delete some existing users
    for i in range(25, 30):
        batch.delete(user_id=f"u{i}")
```

## Automatic Retry

All batch operations include **exponential backoff retry** for unprocessed items (up to 5 retries). This handles DynamoDB throttling transparently — no manual retry logic needed.

## Chunk Sizes

| Operation | Chunk Size | DynamoDB Limit |
|---|---|---|
| `batch_save()` | 25 | 25 items per BatchWriteItem |
| `batch_get()` | 100 | 100 keys per BatchGetItem |
| `batch_delete()` | 25 | 25 items per BatchWriteItem |
| `batch_writer()` | 25 | Auto-flushes at 25 items |
