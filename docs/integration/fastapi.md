# FastAPI Integration

Dynantic models extend Pydantic `BaseModel`, so they work natively with FastAPI.

## Basic CRUD API

```python
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from dynantic import DynamoModel, Key

class User(DynamoModel):
    user_id: str = Key()
    email: EmailStr
    name: str
    age: int
    bio: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Meta:
        table_name = "Users"

class UserCreate(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    age: int
    bio: str | None = None

app = FastAPI()

@app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        **user_data.model_dump(),
        created_at=now,
        updated_at=now,
    )
    user.save()
    return user

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: str) -> User:
    user = User.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str) -> None:
    user = User.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    User.delete(user_id)
```

## Async with Thread Pool

Dynantic is **sync-first**. For async FastAPI endpoints, use `asyncio.to_thread()`:

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    return await asyncio.to_thread(User.get, user_id)

@app.post("/users")
async def create_user(user_data: dict):
    user = User(**user_data)
    await asyncio.to_thread(user.save)
    return user.model_dump()
```

!!! info "Why not native async?"
    1. **Cold start overhead** — async runtimes have higher initialization cost
    2. **Lambda fit** — AWS Lambda is optimized for sync request/response
    3. **Simplicity** — most DynamoDB operations don't benefit from concurrency

## Paginated Responses

```python
from typing import Any
from pydantic import BaseModel
from fastapi import Query

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
