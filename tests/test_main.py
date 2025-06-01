import pytest
from httpx import AsyncClient
from fastapi import status

@pytest.mark.asyncio
async def test_read_root(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Welcome to the SaaS Content Generator API!"}