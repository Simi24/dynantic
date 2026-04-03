# Querying

## Basic Query

```python
# Query by partition key — returns all items with that key
orders = Order.query("customer-456").all()

# First result only
first_order = Order.query("customer-456").first()

# Limit results
recent_orders = Order.query("customer-456").limit(10).all()
```

## Sort Key Conditions

```python
# Exact match
order = Order.query("customer-456").eq("order-789").first()

# Prefix match
posts_2023 = BlogPost.query("author-123").starts_with("2023-").all()

# Range queries
posts = BlogPost.query("author-123").between(
    datetime(2023, 1, 1, tzinfo=timezone.utc),
    datetime(2023, 12, 31, tzinfo=timezone.utc)
).all()

# Comparisons
expensive = Product.query("category").gt(100.0).all()
cheap = Product.query("category").lt(10.0).all()
```

**Available sort key operators:** `eq()`, `starts_with()`, `between()`, `gt()`, `lt()`, `ge()`, `le()`

## GSI Queries

```python
# Query by GSI partition key
tech_posts = BlogPost.query_index("CategoryIndex", "technology").all()

# With sort key condition
recent_tech = BlogPost.query_index("CategoryIndex", "technology") \
    .starts_with("2024-") \
    .limit(20) \
    .all()
```

## Filtering (Non-Key Attributes)

Filters apply **after** DynamoDB retrieves items. Use key conditions whenever possible for better performance.

```python
from dynantic import Attr

# Single filter
high_rated = Movie.query(2013).filter(Attr("rating") >= 8.0).all()

# Multiple filters (combined with AND)
popular_dramas = (
    Movie.query(2013)
    .filter(Attr("rating") >= 8.0)
    .filter(Attr("genres").contains("Drama"))
    .all()
)

# Complex conditions (OR, AND, NOT)
condition = (Attr("rating") >= 8.0) | Attr("genres").contains("Sci-Fi")
movies = Movie.query(2013).filter(condition).all()

# Filter with key condition
results = (
    Movie.query(2013)
    .starts_with("Inter")
    .filter(Attr("rating") < 8.5)
    .all()
)
```

!!! warning "Performance"
    Filters are applied *after* DynamoDB retrieves items, so you still pay for the read capacity of all scanned items. Use key conditions whenever possible.

### Filter Operators

| Operator | Example |
|---|---|
| `==`, `!=`, `<`, `<=`, `>`, `>=` | `Attr("rating") >= 8.0` |
| `.contains()` | `Attr("genres").contains("Drama")` |
| `.begins_with()` | `Attr("title").begins_with("I")` |
| `.exists()` | `Attr("email").exists()` |
| `.not_exists()` | `Attr("deleted_at").not_exists()` |
| `.between()` | `Attr("rating").between(7.0, 9.0)` |
| `.is_in()` | `Attr("status").is_in(["active", "pending"])` |

### Logical Operators

| Operator | Meaning | Example |
|---|---|---|
| `&` | AND | `(Attr("a") > 1) & (Attr("b") < 10)` |
| `\|` | OR | `(Attr("a") > 1) \| (Attr("b") < 10)` |
| `~` | NOT | `~Attr("deleted").exists()` |

## Metaclass DSL vs Attr()

Dynantic provides a metaclass-based DSL that lets you use model fields directly in filter expressions:

```python
# Metaclass DSL — concise, works at runtime
high_rated = Movie.query(2013).filter(Movie.rating >= 8.0).all()

# Attr() — explicit, mypy-compatible
high_rated = Movie.query(2013).filter(Attr("rating") >= 8.0).all()
```

!!! tip "Use `Attr()` in production code"
    Mypy doesn't understand the metaclass DSL (`Movie.rating >= 8.0`) because class attributes are resolved dynamically at runtime. Use `Attr("field_name")` for type-safe code.

## Scanning

Scans read the **entire table** (or index). Use sparingly.

```python
# Scan all items
for user in User.scan():
    print(user.email)

# Scan with limit
for user in User.scan(limit=100):
    process(user)

# Scan with filter
active_users = User.scan().filter(Attr("status") == "active").all()

# Scan GSI
for order in Order.scan(index_name="status-index"):
    print(order.status)
```

!!! warning "Cost"
    Scans consume read capacity proportional to the **total table size**, not the number of results returned. Prefer queries over scans.
