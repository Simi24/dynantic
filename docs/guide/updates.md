# Atomic Updates

Update DynamoDB items **without fetching them first** — saves read capacity and ensures atomicity.

## Basic Usage

```python
# Atomic counter increment
User.update("user-123", "john@example.com") \
    .add(User.login_count, 1) \
    .execute()

# Multiple actions in one request
User.update("user-123", "john@example.com") \
    .set(User.status, "active") \
    .add(User.balance, 10.50) \
    .add(User.tags, {"verified"}) \
    .remove(User.temporary_code) \
    .execute()
```

## Conditional Updates

```python
User.update("user-123", "john@example.com") \
    .set(User.status, "inactive") \
    .condition(User.balance < 0) \
    .execute()
```

Raises `ConditionalCheckFailedError` if the condition is not met.

## Delete Elements from a Set

```python
User.update("user-123", "john@example.com") \
    .delete(User.permissions, {"admin_access"}) \
    .execute()
```

## Return Modified Attributes

```python
updated_user = User.update("user-123", "john@example.com") \
    .add(User.login_count, 1) \
    .return_values("ALL_NEW") \
    .execute()
```

**Return value options:** `"ALL_NEW"`, `"ALL_OLD"`, `"UPDATED_NEW"`, `"UPDATED_OLD"`, `"NONE"`

## Supported Actions

| Action | Description | Example |
|---|---|---|
| `set(field, value)` | Update an attribute | `.set(User.status, "active")` |
| `remove(field)` | Remove an attribute | `.remove(User.temp_code)` |
| `add(field, value)` | Increment number or add to set | `.add(User.balance, 10.0)` |
| `delete(field, value)` | Remove elements from set | `.delete(User.tags, {"old"})` |
| `condition(expr)` | Apply conditional expression | `.condition(User.balance > 0)` |
| `return_values(opt)` | Control what's returned | `.return_values("ALL_NEW")` |
