from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any, Dict
import secrets
from sqlalchemy.orm import Session
from passlib.context import CryptContext # Crucial import
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..core.config import settings
from ..db import models as db_models  # Your SQLAlchemy models

# --- Password Hashing Setup ---
# Kept for potential local password handling, even if Supabase is primary
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- Pydantic Schemas ---
class UserBase(BaseModel):
    email: Optional[EmailStr] = None # Made optional as Supabase might not always provide it or it might be pending verification
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None

class UserInDBBase(UserBase):
    id: int
    is_superuser: bool = False
    model_config = {"from_attributes": True}

class User(UserBase): # Model for API responses (e.g., after registration)
    id: int
    is_active: bool = True
    is_superuser: bool = False
    is_email_verified: bool = False # Default to false, synced from Supabase
    model_config = {"from_attributes": True}

class UserMeResponse(User): # Inherits from User to get basic fields
    subscription_tier: str
    api_call_count: int
    monthly_api_limit: int
    api_limit_reset_at: Optional[datetime] = None # Can be None if not set yet
    model_config = {"from_attributes": True}

class UserUpdateTierRequest(BaseModel):
    user_id: int
    new_tier: str

class UserUpdateActiveStatusRequest(BaseModel):
    user_id: int
    is_active: bool

class UserUpdateMeRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    # To change password, new_password must be provided.
    new_password: Optional[str] = Field(None, min_length=8)

class SubscriptionPlanDetail(BaseModel):
    tier_id: str # e.g., "free", "basic"
    display_name: str
    description: str
    api_calls: int

class UserChangeSubscriptionRequest(BaseModel):
    new_tier: str

# --- DB User Lookup Helpers ---
def get_user_by_email(db: Session, email: str) -> Optional[db_models.User]:
    return db.query(db_models.User).filter(db_models.User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[db_models.User]:
    return db.query(db_models.User).filter(db_models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[db_models.User]:
    return db.query(db_models.User).filter(db_models.User.id == user_id).first()

def get_user_by_supabase_id(db: Session, supabase_id: str) -> Optional[db_models.User]:
    return db.query(db_models.User).filter(db_models.User.supabase_user_id == supabase_id).first()

# --- User Self-Service Profile Update ---
def update_current_user_profile(
    db: Session,
    current_user: db_models.User, # This will be a placeholder user for now
    user_update_in: UserUpdateMeRequest
) -> db_models.User:
    updated = False
    if user_update_in.full_name is not None and user_update_in.full_name != current_user.full_name:
        current_user.full_name = user_update_in.full_name
        updated = True

    if user_update_in.email is not None and user_update_in.email != current_user.email:
        # If email is being changed, ensure it's not taken by another user (excluding self)
        # This check is important even if Supabase handles primary email verification.
        existing_user_with_new_email = get_user_by_email(db, user_update_in.email)
        if existing_user_with_new_email and existing_user_with_new_email.id != current_user.id:
            raise ValueError("Email already registered by another user.")
        current_user.email = user_update_in.email
        # Note: Changing email here might de-sync with Supabase if not handled carefully.
        # Supabase should be the source of truth for email verification status.
        # For now, we allow local update, but `is_email_verified` should be synced from Supabase.
        updated = True

    if user_update_in.new_password is not None:
        # This allows setting/changing a local password.
        # If a user exists only via Supabase and has no local password, this sets one.
        current_user.hashed_password = get_password_hash(user_update_in.new_password)
        updated = True

    if updated:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return current_user

# --- Supabase User Provisioning ---
async def get_or_create_user_from_supabase(
    db: Session,
    supabase_user_id: str,
    email: Optional[str],
    payload: Dict[str, Any] # Decoded Supabase JWT payload
) -> db_models.User:
    """
    Retrieves an existing user by supabase_user_id or creates a new one
    if they don't exist in the local database.
    """
    db_user = get_user_by_supabase_id(db, supabase_id=supabase_user_id)

    if db_user:
        updated = False
        # Sync email if provided and different
        if email and db_user.email != email:
            # Check if the new email is already taken by another local user (excluding self)
            existing_with_new_email = get_user_by_email(db, email)
            if existing_with_new_email and existing_with_new_email.supabase_user_id != supabase_user_id:
                # Log warning, but proceed with Supabase as source of truth for this user's email
                print(f"Warning: Supabase user {supabase_user_id} updated email to {email}, which is used by another local user account. This might require manual reconciliation.")
            db_user.email = email
            updated = True
        
        # Sync email verification status from Supabase
        is_supabase_email_verified = bool(payload.get("email_confirmed_at"))
        if db_user.is_email_verified != is_supabase_email_verified:
            db_user.is_email_verified = is_supabase_email_verified
            updated = True
        
        # Sync full name if available in metadata and different
        supabase_full_name = payload.get("user_metadata", {}).get("full_name")
        if supabase_full_name and db_user.full_name != supabase_full_name:
            db_user.full_name = supabase_full_name
            updated = True

        if updated:
            db.commit()
            db.refresh(db_user)
        return db_user

    # User does not exist locally, create them
    base_username_parts = []
    if email:
        base_username_parts.append(email.split('@')[0])
    else: # Fallback if email is not available (e.g. phone auth, though less common for this setup)
        base_username_parts.append("user")
    
    # Ensure username is unique
    username_candidate = "_".join(filter(None, base_username_parts))
    if not username_candidate: # Should not happen with above logic, but as a safeguard
        username_candidate = f"user_{secrets.token_hex(4)}"
        
    temp_username = username_candidate
    counter = 1
    while get_user_by_username(db, temp_username):
        temp_username = f"{username_candidate}_{counter}"
        counter += 1
    final_username = temp_username

    default_tier_config = settings.SUBSCRIPTION_TIERS_CONFIG.get(settings.DEFAULT_SUBSCRIPTION_TIER, {"api_calls": 0})
    
    new_user = db_models.User(
        supabase_user_id=supabase_user_id,
        email=email,
        username=final_username, # Use the ensured unique username
        full_name=payload.get("user_metadata", {}).get("full_name"),
        is_active=True, # New users from Supabase are active by default
        is_email_verified=bool(payload.get("email_confirmed_at")), # Sync from Supabase
        subscription_tier=settings.DEFAULT_SUBSCRIPTION_TIER,
        monthly_api_limit=default_tier_config.get("api_calls", 0),
        api_limit_reset_at=datetime.now(timezone.utc) + timedelta(days=settings.API_LIMIT_RESET_DAYS),
        # hashed_password is None as Supabase handles auth
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# --- Subscription Management (User) ---
def get_available_subscription_plans() -> List[SubscriptionPlanDetail]:
    """
    Retrieves a list of available subscription plans from settings.
    """
    plans = []
    for tier_id, config in settings.SUBSCRIPTION_TIERS_CONFIG.items():
        plans.append(
            SubscriptionPlanDetail(
                tier_id=tier_id,
                display_name=config.get("display_name", tier_id.capitalize()),
                description=config.get("description", f"Access to {config.get('api_calls', 'N/A')} API calls."),
                api_calls=config.get("api_calls", 0)
            )
        )
    return plans

def change_current_user_subscription_tier(
    db: Session, current_user: db_models.User, new_tier: str # current_user is a placeholder
) -> db_models.User:
    if new_tier not in settings.VALID_SUBSCRIPTION_TIERS:
        raise ValueError(f"Invalid subscription tier: {new_tier}. Valid tiers are: {settings.VALID_SUBSCRIPTION_TIERS}")

    tier_config = settings.SUBSCRIPTION_TIERS_CONFIG[new_tier]
    current_user.subscription_tier = new_tier
    current_user.monthly_api_limit = tier_config.get("api_calls", 0)
    # Reset API call count and reset date upon tier change
    current_user.api_call_count = 0
    current_user.api_limit_reset_at = datetime.now(timezone.utc) + timedelta(days=settings.API_LIMIT_RESET_DAYS)
    db.commit()
    db.refresh(current_user)
    return current_user

# --- User Management (Admin) ---
def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[db_models.User]:
    return db.query(db_models.User).offset(skip).limit(limit).all()

def update_user_subscription_tier(db: Session, user_id: int, new_tier: str) -> Optional[db_models.User]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    if new_tier not in settings.VALID_SUBSCRIPTION_TIERS:
        raise ValueError(f"Invalid subscription tier: {new_tier}. Valid tiers are: {settings.VALID_SUBSCRIPTION_TIERS}")

    tier_config = settings.SUBSCRIPTION_TIERS_CONFIG.get(new_tier)
    if not tier_config:
        raise ValueError(f"Configuration for tier '{new_tier}' not found.")

    user.subscription_tier = new_tier
    user.monthly_api_limit = tier_config.get("api_calls", 0)
    user.api_call_count = 0 # Reset count on admin change too
    user.api_limit_reset_at = datetime.now(timezone.utc) + timedelta(days=settings.API_LIMIT_RESET_DAYS)
    db.commit()
    db.refresh(user)
    return user

def set_user_active_status(db: Session, user_id: int, is_active: bool) -> Optional[db_models.User]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
