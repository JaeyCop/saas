import pytest
from httpx import AsyncClient
from fastapi import status
import uuid # To generate unique usernames/emails for tests
from datetime import datetime, timedelta, timezone # For manipulating token expiry

from src.core.config import settings # To get default tier for assertions
from src.db import models as db_models # For direct DB checks
from src.db.database import SessionLocal # To get a direct DB session for test setup

@pytest.mark.asyncio
async def test_register_new_user_success(async_client: AsyncClient):
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"testuser_{unique_suffix}"
    email = f"test_{unique_suffix}@example.com"
    password = "testpassword123"

    response = await async_client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == email
    assert data["username"] == username
    assert "id" in data
    assert "hashed_password" not in data # Ensure password is not returned
    assert "is_email_verified" in data
    assert data["is_email_verified"] is False # New users should not be verified

    # Check DB for verification token (optional, for deeper testing)
    db = SessionLocal()
    db_user_check = db.query(db_models.User).filter(db_models.User.email == email).first()
    assert db_user_check.email_verification_token is not None
    assert db_user_check.email_verification_token_expires_at is not None
    db.close()
    # We can't easily check subscription_tier here as it's not part of UserResponse
    # but we know it's set by the service.

@pytest.mark.asyncio
async def test_login_for_access_token_success(async_client: AsyncClient):
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"loginuser_{unique_suffix}"
    email = f"login_{unique_suffix}@example.com"
    password = "testpassword123"

    # Register user first
    await async_client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password}
    )

    # Attempt login
    login_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": password} # Login uses form data
    )
    assert login_response.status_code == status.HTTP_200_OK
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_register_user_duplicate_email(async_client: AsyncClient):
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"duplicate_{unique_suffix}@example.com"
    password = "testpassword123"

    # First registration
    await async_client.post(
        "/auth/register",
        json={"username": f"user1_{unique_suffix}", "email": email, "password": password}
    )

    # Attempt to register again with the same email
    response = await async_client.post(
        "/auth/register",
        json={"username": f"user2_{unique_suffix}", "email": email, "password": password}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_incorrect_password(async_client: AsyncClient):
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"wrongpass_user_{unique_suffix}"
    email = f"wrongpass_{unique_suffix}@example.com"
    password = "testpassword123"

    # Register user
    await async_client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password}
    )

    # Attempt login with incorrect password
    login_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": "wrongpassword"}
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in login_response.json()["detail"]

@pytest.mark.asyncio
async def test_login_non_existent_user(async_client: AsyncClient):
    # Attempt login with a username that hasn't been registered
    login_response = await async_client.post(
        "/auth/token",
        data={"username": "nonexistentuser123", "password": "anypassword"}
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in login_response.json()["detail"]

@pytest.mark.asyncio
async def test_register_user_duplicate_username(async_client: AsyncClient):
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"duplicate_user_{unique_suffix}"
    password = "testpassword123"

    # First registration
    await async_client.post(
        "/auth/register",
        json={"username": username, "email": f"email1_{unique_suffix}@example.com", "password": password}
    )

    # Attempt to register again with the same username but different email
    response = await async_client.post(
        "/auth/register",
        json={"username": username, "email": f"email2_{unique_suffix}@example.com", "password": password}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Username already taken" in response.json()["detail"]

@pytest.mark.asyncio
async def test_verify_email_success(async_client: AsyncClient):
    # 1. Register a new user
    user_suffix = uuid.uuid4().hex[:6]
    user_data = {
        "username": f"verifyuser_{user_suffix}",
        "email": f"verify_{user_suffix}@example.com",
        "password": "verifypassword123",
        "full_name": "Verify User"
    }
    register_response = await async_client.post("/auth/register", json=user_data)
    assert register_response.status_code == status.HTTP_201_CREATED
    
    # 2. Get the verification token from the database (simulating email)
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == user_data["email"]).first()
    assert db_user is not None
    assert db_user.email_verification_token is not None
    verification_token = db_user.email_verification_token
    assert not db_user.is_email_verified
    db.close()

    # 3. Call the verify-email endpoint
    verify_response = await async_client.post(f"/auth/verify-email/{verification_token}")
    assert verify_response.status_code == status.HTTP_200_OK
    verified_user_data = verify_response.json()
    assert verified_user_data["email"] == user_data["email"]
    assert verified_user_data["is_email_verified"] is True

    # 4. Check DB that user is verified and token is cleared
    db = SessionLocal()
    db_user_after_verify = db.query(db_models.User).filter(db_models.User.email == user_data["email"]).first()
    assert db_user_after_verify.is_email_verified is True
    assert db_user_after_verify.email_verification_token is None
    assert db_user_after_verify.email_verification_token_expires_at is None
    db.close()

@pytest.mark.asyncio
async def test_verify_email_invalid_token(async_client: AsyncClient):
    invalid_token = "thisisnotavalidtoken12345"
    response = await async_client.post(f"/auth/verify-email/{invalid_token}")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired verification token" in response.json()["detail"]

@pytest.mark.asyncio
async def test_verify_email_expired_token(async_client: AsyncClient):
    # 1. Register user
    user_suffix = uuid.uuid4().hex[:6]
    user_data = {"username": f"expired_{user_suffix}", "email": f"expired_{user_suffix}@example.com", "password": "password123", "full_name": "Expired Token User"}
    await async_client.post("/auth/register", json=user_data)

    # 2. Manually expire the token in DB
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == user_data["email"]).first()
    assert db_user is not None
    token = db_user.email_verification_token
    db_user.email_verification_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()

    # 3. Attempt verification
    response = await async_client.post(f"/auth/verify-email/{token}")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired verification token" in response.json()["detail"]

@pytest.mark.asyncio
async def test_resend_verification_email_success(async_client: AsyncClient, normal_user_token_headers: dict):
    # Ensure the user (from normal_user_token_headers fixture) is not verified for this test
    # We need to fetch the user's email from the token or /me endpoint first
    me_response = await async_client.get("/users/me", headers=normal_user_token_headers)
    user_email = me_response.json()["email"]

    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == user_email).first()
    assert db_user is not None
    db_user.is_email_verified = False
    original_token = db_user.email_verification_token # Could be None or some value
    db.commit()
    db.refresh(db_user) # Refresh to get the committed state
    db.close()

    response = await async_client.post("/auth/resend-verification-email", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["message"] == "If an account with this email exists and is not verified, a new verification link has been sent."

    # Check DB for new token
    db = SessionLocal()
    db_user_after_resend = db.query(db_models.User).filter(db_models.User.email == user_email).first()
    assert db_user_after_resend.email_verification_token is not None
    assert db_user_after_resend.email_verification_token != original_token # Ensure it's a new token
    assert db_user_after_resend.email_verification_token_expires_at is not None
    db.close()

@pytest.mark.asyncio
async def test_resend_verification_email_already_verified(async_client: AsyncClient, normal_user_token_headers: dict):
    # For this test, we assume the user from normal_user_token_headers is already verified.
    # If the fixture doesn't guarantee this, we'd need to set it manually.
    # For simplicity, let's assume the fixture user might not be verified, so we verify them first.
    me_response = await async_client.get("/users/me", headers=normal_user_token_headers)
    user_email = me_response.json()["email"]
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == user_email).first()
    db_user.is_email_verified = True # Manually set to verified
    db.commit()
    db.close()

    response = await async_client.post("/auth/resend-verification-email", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email is already verified" in response.json()["detail"]

# --- Password Reset Tests ---

@pytest.mark.asyncio
async def test_request_password_reset_success(async_client: AsyncClient):
    # 1. Register a user
    user_suffix = uuid.uuid4().hex[:6]
    email = f"resetreq_{user_suffix}@example.com"
    await async_client.post(
        "/auth/register",
        json={"username": f"resetrequser_{user_suffix}", "email": email, "password": "oldpassword123"}
    )

    # 2. Request password reset
    response = await async_client.post("/auth/request-password-reset", json={"email": email})
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["message"] == "If an account with that email exists, a password reset link has been sent."

    # 3. Check DB for reset token (simulating email)
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == email).first()
    assert db_user is not None
    assert db_user.password_reset_token is not None
    assert db_user.password_reset_token_expires_at is not None
    db.close()

@pytest.mark.asyncio
async def test_request_password_reset_non_existent_email(async_client: AsyncClient):
    email = f"nonexistent_{uuid.uuid4().hex[:6]}@example.com"
    response = await async_client.post("/auth/request-password-reset", json={"email": email})
    assert response.status_code == status.HTTP_202_ACCEPTED # Still accepted to prevent enumeration
    assert response.json()["message"] == "If an account with that email exists, a password reset link has been sent."

@pytest.mark.asyncio
async def test_reset_password_success(async_client: AsyncClient):
    # 1. Register user and request reset
    user_suffix = uuid.uuid4().hex[:6]
    username = f"resetconfirm_{user_suffix}"
    email = f"resetconfirm_{user_suffix}@example.com"
    old_password = "oldpassword123"
    new_password = "newStrongPassword456"

    await async_client.post("/auth/register", json={"username": username, "email": email, "password": old_password})
    await async_client.post("/auth/request-password-reset", json={"email": email})

    # 2. Get reset token from DB
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == email).first()
    assert db_user is not None
    reset_token = db_user.password_reset_token
    db.close()
    assert reset_token is not None

    # 3. Reset password with token
    reset_response = await async_client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": new_password}
    )
    assert reset_response.status_code == status.HTTP_200_OK
    assert reset_response.json()["email"] == email # Check if user data is returned

    # 4. Verify old password no longer works
    login_old_pass_response = await async_client.post("/auth/token", data={"username": username, "password": old_password})
    assert login_old_pass_response.status_code == status.HTTP_401_UNAUTHORIZED

    # 5. Verify new password works
    login_new_pass_response = await async_client.post("/auth/token", data={"username": username, "password": new_password})
    assert login_new_pass_response.status_code == status.HTTP_200_OK
    assert "access_token" in login_new_pass_response.json()

    # 6. Check DB that token is cleared
    db = SessionLocal()
    db_user_after_reset = db.query(db_models.User).filter(db_models.User.email == email).first()
    assert db_user_after_reset.password_reset_token is None
    assert db_user_after_reset.password_reset_token_expires_at is None
    db.close()

@pytest.mark.asyncio
async def test_reset_password_invalid_token(async_client: AsyncClient):
    response = await async_client.post(
        "/auth/reset-password",
        json={"token": "invalidtoken123", "new_password": "somepassword123"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired password reset token" in response.json()["detail"]

@pytest.mark.asyncio
async def test_reset_password_expired_token(async_client: AsyncClient):
    # 1. Register, request reset
    user_suffix = uuid.uuid4().hex[:6]
    email = f"resetexpired_{user_suffix}@example.com"
    await async_client.post("/auth/register", json={"username": f"resetexpuser_{user_suffix}", "email": email, "password": "password123"})
    await async_client.post("/auth/request-password-reset", json={"email": email})

    # 2. Get token and manually expire it in DB
    db = SessionLocal()
    db_user = db.query(db_models.User).filter(db_models.User.email == email).first()
    assert db_user is not None
    token = db_user.password_reset_token
    db_user.password_reset_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS + 1)
    db.commit()
    db.close()

    # 3. Attempt reset
    response = await async_client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired password reset token" in response.json()["detail"]