"""User API routes."""

from typing import List

from fastapi import APIRouter, HTTPException, Depends

from app.models.user import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate):
    """Create a new user."""
    return await user_service.create_user(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """Get a user by ID."""
    user = await user_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_model=List[UserResponse])
async def get_users(skip: int = 0, limit: int = 100):
    """Get list of users."""
    return await user_service.get_users(skip=skip, limit=limit)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate):
    """Update a user."""
    updated = await user_service.update_user(user_id, user)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """Delete a user."""
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return None


@router.post("/login")
async def login_user(email: str, password: str):
    """Login user."""
    user = await user_service.authenticate_user(email, password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful", "user_id": user.id}