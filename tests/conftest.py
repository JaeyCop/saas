import pytest
import pytest_asyncio
from typing import Generator, Any, AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine # Make sure this is imported
from sqlalchemy.orm import sessionmaker, Session # Make sure this is imported
import uuid
from fastapi import status

from src.main import app  # Your FastAPI application
from src.core.config import settings
from src.db.database import SessionLocal, Base, get_db # Base might not be strictly needed here but get_db is
from src.services import auth_service # To fetch user for admin promotion
from src.db import models as db_models # For db_models.User type

# This engine could be configured for a separate test database if desired.
# For now, it uses the same DATABASE_URL as the app.
engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency for tests
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="function")
async def db_session_for_fixture() -> AsyncGenerator[Session, None]:
    """Provides a DB session specifically for fixtures that need to manipulate the DB directly."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def normal_user_token_headers(async_client: AsyncClient) -> dict:
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"testnormal_{unique_suffix}"
    email = f"normal_{unique_suffix}@example.com"
    password = "testpassword123"

    reg_response = await async_client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED

    login_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": password}
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def admin_user_token_headers(async_client: AsyncClient, db_session_for_fixture: Session) -> dict:
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"testadmin_{unique_suffix}"
    email = f"admin_{unique_suffix}@example.com"
    password = "testpassword123"

    reg_response = await async_client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password}
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    user_id = reg_response.json()["id"]

    user: db_models.User = db_session_for_fixture.query(db_models.User).filter(db_models.User.id == user_id).first()
    assert user is not None
    user.is_superuser = True
    db_session_for_fixture.commit()

    login_response = await async_client.post(
        "/auth/token",
        data={"username": username, "password": password}
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

