"""
FastAPI Integration Example

Demonstrates that Dynantic models work as Pydantic models in FastAPI.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr

from dynantic import DynamoModel, Key


class User(DynamoModel):
    """User model - works as Pydantic model for FastAPI"""

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
    """Request model for creating a user"""

    user_id: str
    email: EmailStr
    name: str
    age: int
    bio: str | None = None


app = FastAPI(title="Dynantic + FastAPI Example")


@app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate) -> User:
    """Create a new user"""
    now = datetime.now(timezone.utc)
    user = User(
        user_id=user_data.user_id,
        email=user_data.email,
        name=user_data.name,
        age=user_data.age,
        bio=user_data.bio,
        created_at=now,
        updated_at=now,
    )
    user.save()
    return user


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: str) -> User:
    """Get a user by ID"""
    user = User.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found"
        )
    return user


@app.get("/users", response_model=list[User])
def list_users(limit: int = 20) -> list[User]:
    """List users"""
    return list(User.scan().limit(limit))


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str) -> None:
    """Delete a user"""
    user = User.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found"
        )
    User.delete(user_id)


# Run with: uvicorn main:app --reload
# Visit: http://localhost:8000/docs
