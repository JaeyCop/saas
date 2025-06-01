from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# from ...core.security import get_current_user, get_current_active_superuser # Removed as auth is disabled
from ...services import auth_service
from ...services.auth_service import (
    User as UserResponsePydantic,
    UserUpdateTierRequest,
    UserMeResponse,
    UserUpdateActiveStatusRequest,
    UserUpdateMeRequest,
    UserChangeSubscriptionRequest
)
from ...db import models as db_models
from ...db.database import get_db

router = APIRouter()

@router.get("/me", response_model=UserMeResponse, tags=["Users"])
async def read_users_me(
    # current_user: db_models.User = Depends(get_current_user), # Auth disabled
    db: Session = Depends(get_db)
):
    """Get current user."""
    # Placeholder: Fetch the first user as "current_user" since auth is disabled
    # Ensure you have at least one user in your database for this to work.
    # You might want to fetch a specific user by ID (e.g., ID 1) for consistency.
    user = db.query(db_models.User).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found in the database. Please seed your database.")
    return user

@router.patch("/me", response_model=UserMeResponse, tags=["Users"])
async def update_user_me(
    user_update_in: UserUpdateMeRequest,
    # current_user: db_models.User = Depends(get_current_user), # Auth disabled
    db: Session = Depends(get_db)
):
    """Update current User's profile (full name, email, password)."""
    try:
        # Placeholder: Fetch the first user to update
        current_user = db.query(db_models.User).first()
        if not current_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found to update. Please seed your database.")
        updated_user = auth_service.update_current_user_profile(
            db=db,
            current_user=current_user,
            user_update_in=user_update_in
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return updated_user

@router.patch("/me/subscription", response_model=UserMeResponse, tags=["Users", "Subscriptions"])
async def change_my_subscription(
    subscription_request: UserChangeSubscriptionRequest,
    # current_user: db_models.User = Depends(get_current_user), # Auth disabled
    db: Session = Depends(get_db)
):
    """Change authenticated user's subscription tier (Payment processing currently skipped)."""
    try:
        # Placeholder: Fetch the first user to update subscription
        current_user = db.query(db_models.User).first()
        if not current_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found to update subscription. Please seed your database.")
        updated_user = auth_service.change_current_user_subscription_tier(
            db=db,
            current_user=current_user,
            new_tier=subscription_request.new_tier
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return updated_user

@router.get("/", response_model=List[UserResponsePydantic], tags=["Users", "Admin"])
async def read_all_users(
    skip: int = 0,
    limit: int = 100,
    # current_user: db_models.User = Depends(get_current_active_superuser), # Auth disabled, admin route unprotected
    db: Session = Depends(get_db)
):
    """Retrieve all users (Admin/Superuser access required)."""
    users = auth_service.get_users(db=db, skip=skip, limit=limit)
    return users

@router.patch("/update-tier", response_model=UserResponsePydantic, tags=["Users", "Admin"])
async def admin_update_user_tier(
    tier_update_request: UserUpdateTierRequest,
    # current_user: db_models.User = Depends(get_current_active_superuser), # Auth disabled, admin route unprotected
    db: Session = Depends(get_db)
):
    """Update a user's subscription tier (Admin/Superuser access required)."""
    try:
        updated_user = auth_service.update_user_subscription_tier(
            db=db,
            user_id=tier_update_request.user_id,
            new_tier=tier_update_request.new_tier
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {tier_update_request.user_id} not found."
        )
    return updated_user

@router.patch("/set-active-status", response_model=UserResponsePydantic, tags=["Users", "Admin"])
async def admin_set_user_active_status(
    active_status_request: UserUpdateActiveStatusRequest,
    # current_user: db_models.User = Depends(get_current_active_superuser), # Auth disabled, admin route unprotected
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user (Admin/Superuser access required)."""
    updated_user = auth_service.set_user_active_status(
        db=db,
        user_id=active_status_request.user_id,
        is_active=active_status_request.is_active
    )
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {active_status_request.user_id} not found."
        )
    return updated_user