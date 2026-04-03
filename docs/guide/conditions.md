# Conditional Writes

Dynantic provides an SQLModel-like DSL for conditional operations on DynamoDB.

## Basic Conditions

```python
from dynantic import Attr

# Create-if-not-exists
user = User(user_id="u1", email="test@example.com")
user.save(condition=User.email.not_exists())

# Optimistic locking
user.save(condition=User.version == 5)

# Conditional delete
User.delete("u1", condition=(User.balance == 0) & (User.status == "inactive"))
```

## Complex Conditions

```python
# Combine multiple conditions
condition = (User.age >= 18) & (User.status == "active") & ~User.is_banned.exists()
user.save(condition=condition)

# Dynamic field names with Attr()
User.delete("u1", condition=Attr("legacy_field").not_exists())
```

## Comparison Operators

| Operator | Example |
|---|---|
| `==`, `!=` | `User.status == "active"` |
| `<`, `<=`, `>`, `>=` | `User.age >= 18` |
| `.exists()` | `User.email.exists()` |
| `.not_exists()` | `User.deleted_at.not_exists()` |
| `.begins_with(prefix)` | `User.name.begins_with("A")` |
| `.contains(value)` | `User.tags.contains("premium")` |
| `.between(low, high)` | `User.age.between(18, 65)` |
| `.is_in([values])` | `User.status.is_in(["active", "pending"])` |

## Logical Operators

| Operator | Meaning | Example |
|---|---|---|
| `&` | AND | `(User.age >= 18) & (User.active == True)` |
| `\|` | OR | `(User.role == "admin") \| (User.role == "super")` |
| `~` | NOT | `~User.is_banned.exists()` |

!!! tip "Use `Attr()` for mypy compatibility"
    The metaclass DSL (`User.status == "active"`) works at runtime but mypy doesn't understand it. Use `Attr("status") == "active"` for type-safe code.
