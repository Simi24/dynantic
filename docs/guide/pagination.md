# Pagination

External pagination lets your API return cursors to clients for stateless pagination.

## Query Pagination

```python
# Get first page
page1 = Order.query("customer-456").limit(10).page()

print(f"Items: {len(page1.items)}, Has more: {page1.has_more}")

# Get next page using cursor
if page1.has_more:
    page2 = Order.query("customer-456").limit(10).page(start_key=page1.last_evaluated_key)
```

## Scan Pagination

```python
# First page
page1 = Product.scan().limit(25).page()

# Next page
if page1.has_more:
    page2 = Product.scan().limit(25).page(start_key=page1.last_evaluated_key)
```

## PageResult

The `page()` method returns a `PageResult` object:

| Attribute | Type | Description |
|---|---|---|
| `items` | `list[Model]` | Items in the current page |
| `last_evaluated_key` | `dict \| None` | Cursor for the next page |
| `has_more` | `bool` | Whether more pages exist |

## FastAPI Integration

```python
from fastapi import FastAPI, Query
from typing import Any
from pydantic import BaseModel

app = FastAPI()

class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: dict[str, Any] | None
    has_more: bool

@app.get("/orders/{customer_id}")
def get_orders(
    customer_id: str,
    limit: int = Query(default=20, le=100),
    cursor: dict[str, Any] | None = None
) -> PaginatedResponse:
    page = Order.query(customer_id).limit(limit).page(start_key=cursor)

    return PaginatedResponse(
        items=[order.model_dump() for order in page.items],
        next_cursor=page.last_evaluated_key,
        has_more=page.has_more
    )
```

!!! tip "Security"
    Pagination cursors contain DynamoDB key values. If exposing them to clients, consider encrypting or signing them to prevent tampering.
