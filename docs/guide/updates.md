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

## Functional Updates

### Atomic increment

A numeric `add()` is an atomic increment/decrement — no read needed:

```python
# Increment by 1, decrement with a negative value
User.update("user-123").add(User.login_count, 1).execute()
User.update("user-123").add(User.credits, -5).execute()
```

### Set only if absent (`if_not_exists`)

Writes the value only when the attribute doesn't already exist — handy for
initializing a field once without overwriting it on later updates:

```python
User.update("user-123") \
    .set_if_not_exists(User.created_at, datetime.now(timezone.utc)) \
    .execute()
```

### Append to a list (`list_append`)

Appends items to an existing list attribute (the value must be a list):

```python
User.update("user-123") \
    .append(User.events, ["login"]) \
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
| `set_if_not_exists(field, value)` | Set only if attribute is absent | `.set_if_not_exists(User.created_at, now)` |
| `append(field, list)` | Append to a list (`list_append`) | `.append(User.events, ["login"])` |
| `remove(field)` | Remove an attribute | `.remove(User.temp_code)` |
| `add(field, value)` | Increment number or add to set | `.add(User.balance, 10.0)` |
| `delete(field, value)` | Remove elements from set | `.delete(User.tags, {"old"})` |
| `condition(expr)` | Apply conditional expression | `.condition(User.balance > 0)` |
| `return_values(opt)` | Control what's returned | `.return_values("ALL_NEW")` |
