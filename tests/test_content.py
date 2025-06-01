import pytest
from httpx import AsyncClient
from fastapi import status
import uuid # For unique user generation
from sqlalchemy.orm import Session # For type hinting db_session

from src.schemas.content_schemas import TitleRequest, TitleResponse # For request/response validation
from src.db import models as db_models # To fetch User model for DB operations
from src.core.config import settings # To access default tier if needed

@pytest.mark.asyncio
async def test_generate_title_success(async_client: AsyncClient, normal_user_token_headers: dict):
    payload = {
        "topic": "The Future of AI in Software Development",
        "keywords": ["artificial intelligence", "coding", "automation"],
        "style": "thought-provoking"
    }
    response = await async_client.post("/content/generate-title", headers=normal_user_token_headers, json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "generated_title" in data
    assert isinstance(data["generated_title"], str)
    assert len(data["generated_title"]) > 0 # Basic check that a title was generated
    # Further checks could involve ensuring keywords are present if the AI is good enough

@pytest.mark.asyncio
async def test_generate_title_no_token(async_client: AsyncClient):
    payload = {
        "topic": "The Future of AI",
    }
    response = await async_client.post("/content/generate-title", json=payload) # No headers
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_generate_title_invalid_token(async_client: AsyncClient):
    payload = {
        "topic": "The Future of AI",
    }
    headers = {"Authorization": "Bearer aninvalidtoken"}
    response = await async_client.post("/content/generate-title", headers=headers, json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Could not validate credentials"

@pytest.mark.asyncio
async def test_generate_title_missing_topic(async_client: AsyncClient, normal_user_token_headers: dict):
    payload = {} # Missing 'topic'
    response = await async_client.post("/content/generate-title", headers=normal_user_token_headers, json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Pydantic validation error
    # Check for detail about missing field, structure might vary slightly
    assert "Field required" in str(response.json()["detail"]) # Or more specific check

@pytest.mark.asyncio
async def test_api_rate_limit_enforced(async_client: AsyncClient, db_session_for_fixture: Session):
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"ratelimituser_{unique_suffix}"
    email = f"ratelimit_{unique_suffix}@example.com"
    password = "testpassword123"

    # 1. Register user
    reg_response = await async_client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    user_id = reg_response.json()["id"]

    # 2. Login user
    login_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": password}
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Update user's API limit directly in DB for this test
    test_api_limit = 2
    user_in_db = db_session_for_fixture.query(db_models.User).filter(db_models.User.id == user_id).first()
    assert user_in_db is not None
    user_in_db.monthly_api_limit = test_api_limit
    user_in_db.api_call_count = 0 # Ensure count starts at 0 for the test
    db_session_for_fixture.commit()
    db_session_for_fixture.refresh(user_in_db)

    # 4. Make calls up to the limit
    title_payload = {"topic": "Testing Rate Limits"}
    for i in range(test_api_limit):
        response = await async_client.post("/content/generate-title", headers=headers, json=title_payload)
        assert response.status_code == status.HTTP_200_OK, f"Call {i+1} failed unexpectedly"

    # 5. Make one more call - this one should be rate-limited
    response_over_limit = await async_client.post("/content/generate-title", headers=headers, json=title_payload)
    assert response_over_limit.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert f"API call limit of {test_api_limit} exceeded" in response_over_limit.json()["detail"]

    # 6. (Optional) Verify api_call_count via /users/me
    me_response = await async_client.get("/users/me", headers=headers)
    assert me_response.status_code == status.HTTP_200_OK
    me_data = me_response.json()
    assert me_data["api_call_count"] == test_api_limit