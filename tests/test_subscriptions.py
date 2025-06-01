import pytest
from httpx import AsyncClient
from fastapi import status

from src.core.config import settings # To verify against config
from src.services.auth_service import SubscriptionPlanDetail # Pydantic model for response

@pytest.mark.asyncio
async def test_list_available_subscription_plans(async_client: AsyncClient):
    response = await async_client.get("/subscriptions/plans")
    assert response.status_code == status.HTTP_200_OK
    
    plans_data = response.json()
    assert isinstance(plans_data, list)
    
    # Check if the number of plans matches the config
    assert len(plans_data) == len(settings.SUBSCRIPTION_TIERS_CONFIG)
    
    # Check the structure and content of each plan
    for plan_dict in plans_data:
        # Validate with Pydantic model (optional, but good practice)
        SubscriptionPlanDetail(**plan_dict) 
        
        assert "tier_id" in plan_dict
        assert plan_dict["tier_id"] in settings.SUBSCRIPTION_TIERS_CONFIG
        config_tier = settings.SUBSCRIPTION_TIERS_CONFIG[plan_dict["tier_id"]]
        assert plan_dict["display_name"] == config_tier["display_name"]
        assert plan_dict["api_calls"] == config_tier["api_calls"]
        assert plan_dict["description"] == config_tier["description"]