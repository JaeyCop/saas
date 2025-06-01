from fastapi import APIRouter, Depends
from typing import List

from ...services import auth_service # For Pydantic models and service functions
from ...db import models as db_models # For User model type hint
# # To ensure user is authenticated

router = APIRouter()

@router.get(
    "/plans",
    response_model=List[auth_service.SubscriptionPlanDetail],
    tags=["Subscriptions"]
)
async def list_available_subscription_plans(
    # current_user: db_models.User = Depends(get_current_user) # Optional: make it auth-only
):
    """
    Get a list of all available subscription plans.
    Currently, this is open, but can be restricted to authenticated users if needed.
    """
    return auth_service.get_available_subscription_plans()