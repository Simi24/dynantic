# Model Definition

Every Dynantic model extends `DynamoModel` and maps to a DynamoDB table.

## Basic Model (Partition Key Only)

```python
from dynantic import DynamoModel, Key

class Product(DynamoModel):
    product_id: str = Key()
    name: str
    price: float
    in_stock: bool

    class Meta:
        table_name = "products"
```

## Composite Key (Partition + Sort Key)

```python
from dynantic import DynamoModel, Key, SortKey

class Order(DynamoModel):
    customer_id: str = Key()
    order_id: str = SortKey()
    total: float
    items: list[str]

    class Meta:
        table_name = "orders"
```

## Global Secondary Index (GSI)

```python
from dynantic import DynamoModel, Key, SortKey, GSIKey, GSISortKey

class BlogPost(DynamoModel):
    post_id: str = Key()
    author_id: str = SortKey()
    title: str
    content: str
    published_at: datetime

    # GSI for querying by category + slug
    category: str = GSIKey(index_name="CategoryIndex")
    slug: str = GSISortKey(index_name="CategoryIndex")

    class Meta:
        table_name = "blog_posts"
```

Query GSIs with `query_index()`:

```python
tech_posts = BlogPost.query_index("CategoryIndex", "technology").all()
```

### Multiple GSIs

A single model can have multiple GSIs. A field can participate in multiple indexes using the `|` operator:

```python
from datetime import date
from dynantic import DynamoModel, Key, GSIKey, GSISortKey

class Employee(DynamoModel):
    employee_id: str = Key()
    first_name: str
    last_name: str

    # GSI 1: Query by department + hire_date
    department: str = GSIKey(index_name="DepartmentIndex")
    hire_date: date = GSISortKey(index_name="DepartmentIndex") | GSIKey(index_name="HireDateIndex")

    # GSI 2: Query by status + location
    status: str = GSIKey(index_name="StatusLocationIndex")
    location: str = GSISortKey(index_name="StatusLocationIndex")

    class Meta:
        table_name = "employees"
```

## Supported Types

| Python Type | DynamoDB Type | Notes |
|---|---|---|
| `str` | S | |
| `int` | N | |
| `float` | N | |
| `Decimal` | N | Recommended for monetary values |
| `bool` | BOOL | |
| `bytes` | B | |
| `datetime` | S | ISO 8601 format |
| `date` | S | ISO 8601 format |
| `UUID` | S | String representation |
| `Enum` | S | Stored as `.value` |
| `list[T]` | L | Nested types supported |
| `dict[str, T]` | M | Nested maps |
| `set[str]` | SS | String set |
| `set[int]` | NS | Number set |
| `Optional[T]` | — | `None` omits the attribute |

## Meta Class Options

The `Meta` inner class configures the table mapping:

```python
class Meta:
    table_name = "my_table"  # Required: DynamoDB table name
```

!!! note
    Table creation is **not** handled by Dynantic. Use Terraform, CDK, or AWS Console to create tables with the appropriate key schema and GSI definitions.
