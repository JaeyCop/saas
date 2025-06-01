import pytest
from httpx import AsyncClient
from fastapi import status
import uuid # For unique user generation in new tests
from typing import List # For type hinting response
from sqlalchemy.orm import Session # For type hinting db_session in new tests

from src.core.config import settings # For checking default tier, valid tiers
from src.services.auth_service import UserMeResponse, User as UserResponsePydantic, UserUpdateTierRequest, UserUpdateActiveStatusRequest # Import Pydantic models

@pytest.mark.asyncio
async def test_read_users_me_success(async_client: AsyncClient, normal_user_token_headers: dict):
    headers = normal_user_token_headers
    response = await async_client.get("/users/me", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # We don't have the exact email/username from the fixture easily here,
    # but we can check for the presence and type of fields.
    assert "email" in data
    assert "username" in data
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data
    # Check for new fields from UserMeResponse
    assert "subscription_tier" in data
    assert data["subscription_tier"] == settings.DEFAULT_SUBSCRIPTION_TIER
    assert "api_call_count" in data
    assert "monthly_api_limit" in data
    assert "api_limit_reset_at" in data

@pytest.mark.asyncio
async def test_read_users_me_no_token(async_client: AsyncClient):
    response = await async_client.get("/users/me") # No headers
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_read_users_me_invalid_token(async_client: AsyncClient):
    headers = {"Authorization": "Bearer aninvalidtoken"}
    response = await async_client.get("/users/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Could not validate credentials"

@pytest.mark.asyncio
async def test_read_users_me_malformed_token(async_client: AsyncClient):
    headers = {"Authorization": "Bear aninvalidtoken"} # "Bear" instead of "Bearer"
    response = await async_client.get("/users/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # The detail might vary slightly depending on FastAPI's exact parsing of malformed Bearer tokens
    # but it should indicate an authentication failure.
    # Often it's "Not authenticated" if the scheme isn't recognized.
    assert "Not authenticated" in response.json()["detail"] or "Could not validate credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_read_all_users_as_admin_success(async_client: AsyncClient, admin_user_token_headers: dict):
    headers = admin_user_token_headers
    response = await async_client.get("/users/", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    # At least the admin user itself should be in the list
    assert len(data) >= 1
    # Check structure of one item (assuming UserResponsePydantic is the model)
    if data:
        first_user = data[0]
        assert "id" in first_user
        assert "email" in first_user
        assert "username" in first_user
        assert "is_superuser" in first_user # admin endpoint returns this
        assert "hashed_password" not in first_user

@pytest.mark.asyncio
async def test_read_all_users_as_normal_user_forbidden(async_client: AsyncClient, normal_user_token_headers: dict):
    headers = normal_user_token_headers
    response = await async_client.get("/users/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_read_all_users_no_token_unauthorized(async_client: AsyncClient):
    response = await async_client.get("/users/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_admin_update_user_tier_success(async_client: AsyncClient, admin_user_token_headers: dict, db_session_for_fixture: Session):
    # Register a target user whose tier will be updated
    target_user_suffix = uuid.uuid4().hex[:8]
    target_username = f"targettier_{target_user_suffix}"
    target_email = f"targettier_{target_user_suffix}@example.com"
    target_password = "testpassword123"

    reg_response = await async_client.post(
        "/auth/register",
        json={"username": target_username, "email": target_email, "password": target_password}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    target_user_data = reg_response.json()
    target_user_id = target_user_data["id"]

    # Admin updates the tier
    new_tier = "premium" # Assuming "premium" is a valid tier in your settings.SUBSCRIPTION_TIERS_CONFIG
    if new_tier not in settings.VALID_SUBSCRIPTION_TIERS:
        pytest.skip(f"Skipping test, tier '{new_tier}' not in VALID_SUBSCRIPTION_TIERS: {settings.VALID_SUBSCRIPTION_TIERS}")

    update_tier_payload = {"user_id": target_user_id, "new_tier": new_tier}
    response = await async_client.patch("/users/update-tier", headers=admin_user_token_headers, json=update_tier_payload)

    assert response.status_code == status.HTTP_200_OK
    updated_user_data = response.json()
    assert updated_user_data["id"] == target_user_id
    # The UserResponsePydantic (which /update-tier returns) might not have subscription_tier.
    # We need to verify the change by fetching the user's details via /users/me.
    
    # Login as the target user to fetch their /me details
    login_response = await async_client.post("/auth/token", data={"username": target_username, "password": target_password})
    assert login_response.status_code == status.HTTP_200_OK
    target_user_token = login_response.json()["access_token"]
    
    me_response = await async_client.get("/users/me", headers={"Authorization": f"Bearer {target_user_token}"})
    assert me_response.status_code == status.HTTP_200_OK
    me_data = me_response.json()
    assert me_data["subscription_tier"] == new_tier
    expected_limit = settings.SUBSCRIPTION_TIERS_CONFIG[new_tier]["api_calls"]
    assert me_data["monthly_api_limit"] == expected_limit

@pytest.mark.asyncio
async def test_admin_set_user_active_status_success(async_client: AsyncClient, admin_user_token_headers: dict, db_session_for_fixture: Session):
    # Register a target user whose status will be updated
    target_user_suffix = uuid.uuid4().hex[:8]
    target_username = f"targetactive_{target_user_suffix}"
    target_email = f"targetactive_{target_user_suffix}@example.com"
    target_password = "testpassword123"

    reg_response = await async_client.post(
        "/auth/register",
        json={"username": target_username, "email": target_email, "password": target_password}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    target_user_data = reg_response.json()
    target_user_id = target_user_data["id"]
    assert target_user_data["is_active"] is True # Initially active

    # Admin deactivates the user
    update_status_payload = {"user_id": target_user_id, "is_active": False}
    response = await async_client.patch("/users/set-active-status", headers=admin_user_token_headers, json=update_status_payload)

    assert response.status_code == status.HTTP_200_OK
    updated_user_data = response.json()
    assert updated_user_data["id"] == target_user_id
    assert updated_user_data["is_active"] is False

    # Verify user cannot log in (get_current_user checks for active status)
    login_response = await async_client.post(
        "/auth/token",
        data={"username": target_username, "password": target_password}
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED # authenticate_user returns None for inactive users

    # Admin reactivates the user
    update_status_payload_reactivate = {"user_id": target_user_id, "is_active": True}
    response_reactivate = await async_client.patch("/users/set-active-status", headers=admin_user_token_headers, json=update_status_payload_reactivate)
    assert response_reactivate.status_code == status.HTTP_200_OK
    assert response_reactivate.json()["is_active"] is True

    # Verify user can log in again
    login_response_reactivated = await async_client.post(
        "/auth/token",
        data={"username": target_username, "password": target_password}
    )
    assert login_response_reactivated.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_normal_user_cannot_update_tier(async_client: AsyncClient, normal_user_token_headers: dict):
    # Attempt to update tier as a normal user (should be forbidden)
    update_tier_payload = {"user_id": 1, "new_tier": "premium"} # user_id doesn't matter much here
    response = await async_client.patch("/users/update-tier", headers=normal_user_token_headers, json=update_tier_payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_admin_update_user_tier_invalid_tier(async_client: AsyncClient, admin_user_token_headers: dict):
    # Register a target user
    target_user_suffix = uuid.uuid4().hex[:8]
    reg_response = await async_client.post(
        "/auth/register",
        json={"username": f"invtier_{target_user_suffix}", "email": f"invtier_{target_user_suffix}@example.com", "password": "validpassword123"}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    target_user_id = reg_response.json()["id"]

    update_tier_payload = {"user_id": target_user_id, "new_tier": "non_existent_tier"}
    response = await async_client.patch("/users/update-tier", headers=admin_user_token_headers, json=update_tier_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid subscription tier" in response.json()["detail"]

@pytest.mark.asyncio
async def test_admin_update_user_tier_non_existent_user(async_client: AsyncClient, admin_user_token_headers: dict):
    update_tier_payload = {"user_id": 999999, "new_tier": "premium"} # Non-existent user ID
    response = await async_client.patch("/users/update-tier", headers=admin_user_token_headers, json=update_tier_payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User with ID 999999 not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_normal_user_cannot_set_active_status(async_client: AsyncClient, normal_user_token_headers: dict):
    # Attempt to set active status as a normal user (should be forbidden)
    update_status_payload = {"user_id": 1, "is_active": False} # user_id doesn't matter much
    response = await async_client.patch("/users/set-active-status", headers=normal_user_token_headers, json=update_status_payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_admin_set_user_active_status_non_existent_user(async_client: AsyncClient, admin_user_token_headers: dict):
    update_status_payload = {"user_id": 999999, "is_active": False} # Non-existent user ID
    response = await async_client.patch("/users/set-active-status", headers=admin_user_token_headers, json=update_status_payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User with ID 999999 not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_users_me_full_name_success(async_client: AsyncClient, normal_user_token_headers: dict):
    new_full_name = f"Updated Name {uuid.uuid4().hex[:4]}"
    payload = {"full_name": new_full_name}
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == new_full_name

    # Verify by fetching /me again
    me_response = await async_client.get("/users/me", headers=normal_user_token_headers)
    assert me_response.json()["full_name"] == new_full_name

@pytest.mark.asyncio
async def test_update_users_me_email_success(async_client: AsyncClient, normal_user_token_headers: dict):
    new_email = f"new_email_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": new_email}
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == new_email

    # Verify by fetching /me again
    me_response = await async_client.get("/users/me", headers=normal_user_token_headers)
    assert me_response.json()["email"] == new_email

@pytest.mark.asyncio
async def test_update_users_me_password_success(async_client: AsyncClient, normal_user_token_headers: dict, db_session_for_fixture: Session):
    # Get current user's username to re-login
    me_response_before = await async_client.get("/users/me", headers=normal_user_token_headers)
    username = me_response_before.json()["username"]
    original_password = "testpassword123" # from fixture

    new_password = f"newStrongPassword{uuid.uuid4().hex[:4]}"
    payload = {"new_password": new_password}
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK

    # Try to login with the old password (should fail)
    login_old_pass_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": original_password}
    )
    assert login_old_pass_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Try to login with the new password (should succeed)
    login_new_pass_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": new_password}
    )
    assert login_new_pass_response.status_code == status.HTTP_200_OK
    assert "access_token" in login_new_pass_response.json()

@pytest.mark.asyncio
async def test_update_users_me_all_fields_success(async_client: AsyncClient, normal_user_token_headers: dict):
    me_response_before = await async_client.get("/users/me", headers=normal_user_token_headers)
    username = me_response_before.json()["username"]
    original_password = "testpassword123"

    new_full_name = f"Full Update Name {uuid.uuid4().hex[:4]}"
    new_email = f"full_update_{uuid.uuid4().hex[:8]}@example.com"
    new_password = f"fullUpdatePass{uuid.uuid4().hex[:4]}"

    payload = {
        "full_name": new_full_name,
        "email": new_email,
        "new_password": new_password
    }
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == new_full_name
    assert data["email"] == new_email

    # Verify by fetching /me again (need new token after password change)
    login_new_pass_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": new_password} # Use original username if not changed, or new email
    )
    assert login_new_pass_response.status_code == status.HTTP_200_OK
    new_token = login_new_pass_response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    me_response_after = await async_client.get("/users/me", headers=new_headers)
    assert me_response_after.json()["full_name"] == new_full_name
    assert me_response_after.json()["email"] == new_email

@pytest.mark.asyncio
async def test_update_users_me_email_conflict(async_client: AsyncClient, normal_user_token_headers: dict, admin_user_token_headers: dict):
    # Get admin's email (or any other existing user's email)
    admin_me_response = await async_client.get("/users/me", headers=admin_user_token_headers)
    admin_email = admin_me_response.json()["email"]

    # Normal user tries to update their email to the admin's email
    payload = {"email": admin_email}
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered by another user" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_users_me_invalid_password_format(async_client: AsyncClient, normal_user_token_headers: dict):
    payload = {"new_password": "short"} # Password too short
    response = await async_client.patch("/users/me", headers=normal_user_token_headers, json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Check for detail about password length
    assert "Password must be at least 8 characters long" in str(response.json()["detail"]).lower() # Example check

@pytest.mark.asyncio
async def test_update_users_me_no_token(async_client: AsyncClient):
    payload = {"full_name": "No Token Update"}
    response = await async_client.patch("/users/me", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_admin_update_self_tier_success(async_client: AsyncClient, admin_user_token_headers: dict, db_session_for_fixture: Session):
    # Get admin user's ID from their token (a bit indirect, but works for testing)
    me_response_before = await async_client.get("/users/me", headers=admin_user_token_headers)
    assert me_response_before.status_code == status.HTTP_200_OK
    admin_user_id = me_response_before.json()["id"]
    original_tier = me_response_before.json()["subscription_tier"]

    # Determine a new tier that is different from the current one
    new_tier = "premium" if original_tier != "premium" else "basic"
    if new_tier not in settings.VALID_SUBSCRIPTION_TIERS:
         # if basic is not a valid tier, try free, or skip if only one tier exists
        new_tier = "free" if "free" in settings.VALID_SUBSCRIPTION_TIERS and original_tier != "free" else None
        if not new_tier or new_tier == original_tier:
            pytest.skip(f"Cannot find a different valid tier to switch to from {original_tier}. Valid: {settings.VALID_SUBSCRIPTION_TIERS}")


    update_tier_payload = {"user_id": admin_user_id, "new_tier": new_tier}
    response = await async_client.patch("/users/update-tier", headers=admin_user_token_headers, json=update_tier_payload)

    assert response.status_code == status.HTTP_200_OK
    updated_user_data = response.json()
    assert updated_user_data["id"] == admin_user_id
    
    # Verify the change by fetching the admin's /me details again
    me_response_after = await async_client.get("/users/me", headers=admin_user_token_headers)
    assert me_response_after.status_code == status.HTTP_200_OK
    me_data_after = me_response_after.json()
    assert me_data_after["subscription_tier"] == new_tier
    expected_limit = settings.SUBSCRIPTION_TIERS_CONFIG[new_tier]["api_calls"]
    assert me_data_after["monthly_api_limit"] == expected_limit

@pytest.mark.asyncio
async def test_user_change_own_subscription_success(async_client: AsyncClient, normal_user_token_headers: dict):
    # Get current tier
    me_response_before = await async_client.get("/users/me", headers=normal_user_token_headers)
    assert me_response_before.status_code == status.HTTP_200_OK
    original_tier = me_response_before.json()["subscription_tier"]

    # Determine a new tier that is different from the current one
    new_tier = "premium" # Default to premium
    if original_tier == "premium":
        new_tier = "basic"
    
    if new_tier not in settings.VALID_SUBSCRIPTION_TIERS:
         pytest.skip(f"Skipping test, tier '{new_tier}' not in VALID_SUBSCRIPTION_TIERS: {settings.VALID_SUBSCRIPTION_TIERS}")

    payload = {"new_tier": new_tier}
    response = await async_client.patch("/users/me/subscription", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["subscription_tier"] == new_tier
    expected_limit = settings.SUBSCRIPTION_TIERS_CONFIG[new_tier]["api_calls"]
    assert data["monthly_api_limit"] == expected_limit

    # Verify by fetching /me again
    me_response_after = await async_client.get("/users/me", headers=normal_user_token_headers)
    assert me_response_after.status_code == status.HTTP_200_OK
    assert me_response_after.json()["subscription_tier"] == new_tier
    assert me_response_after.json()["monthly_api_limit"] == expected_limit

@pytest.mark.asyncio
async def test_user_change_own_subscription_invalid_tier(async_client: AsyncClient, normal_user_token_headers: dict):
    invalid_tier = "non_existent_tier_123"
    payload = {"new_tier": invalid_tier}
    response = await async_client.patch("/users/me/subscription", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert f"Invalid subscription tier: {invalid_tier}" in response.json()["detail"]

@pytest.mark.asyncio
async def test_user_change_own_subscription_no_token(async_client: AsyncClient):
    payload = {"new_tier": "basic"}
    response = await async_client.patch("/users/me/subscription", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_user_change_own_subscription_to_same_tier(async_client: AsyncClient, normal_user_token_headers: dict):
    me_response = await async_client.get("/users/me", headers=normal_user_token_headers)
    current_tier = me_response.json()["subscription_tier"]
    payload = {"new_tier": current_tier} # Attempt to change to the same tier
    response = await async_client.patch("/users/me/subscription", headers=normal_user_token_headers, json=payload)
    assert response.status_code == status.HTTP_200_OK # Should still be successful, no actual change needed
    assert response.json()["subscription_tier"] == current_tier