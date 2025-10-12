"""
Integration tests for authentication endpoints.

Tests: /auth/register, /auth/login, /auth/me
"""

import pytest


@pytest.mark.asyncio
class TestAuthRegister:
    """Test POST /auth/register endpoint."""

    async def test_register_success(self, async_client, test_company):
        """Test successful user registration."""
        import time

        email = f"newuser{int(time.time())}@example.com"

        response = await async_client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "SecurePass123!",
                "first_name": "New",
                "last_name": "User",
                "company_code": test_company.invite_code,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == email
        assert data["user"]["first_name"] == "New"
        assert data["user"]["last_name"] == "User"
        assert "access_token" in data

    async def test_register_invalid_company_code(self, async_client):
        """Test registration with invalid company code."""
        response = await async_client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "SecurePass123!",
                "first_name": "User",
                "last_name": "Test",
                "company_code": "INVALID-code",
            },
        )

        assert response.status_code == 404
        assert "company not found" in response.json()["error"]["message"].lower()

    async def test_register_duplicate_email(self, async_client, create_test_user, test_company):
        """Test registration with existing email."""
        # Create a user first
        user = await create_test_user()

        # Try to register again with same email
        response = await async_client.post(
            "/auth/register",
            json={
                "email": user["email"],
                "password": "SecurePass123!",
                "first_name": "Another",
                "last_name": "User",
                "company_code": test_company.invite_code,
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["error"]["message"].lower()

    async def test_register_invalid_email(self, async_client, test_company):
        """Test registration with invalid email format."""
        response = await async_client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "first_name": "User",
                "last_name": "Test",
                "company_code": test_company.invite_code,
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestAuthLogin:
    """Test POST /auth/login endpoint."""

    async def test_login_success(self, async_client, create_test_user):
        """Test successful login."""
        # Create a user first
        user = await create_test_user()

        response = await async_client.post(
            "/auth/login",
            json={
                "email": user["email"],
                "password": "TestPass123!",  # From create_test_user helper
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == user["email"]
        assert "access_token" in data

    async def test_login_wrong_password(self, async_client, create_test_user):
        """Test login with wrong password."""
        # Create a user first
        user = await create_test_user()

        response = await async_client.post(
            "/auth/login",
            json={
                "email": user["email"],
                "password": "wrong_password",
            },
        )

        assert response.status_code == 401
        assert (
            "invalid credentials" in response.json()["error"]["message"].lower()
            or "invalid email or password" in response.json()["error"]["message"].lower()
        )

    async def test_login_nonexistent_user(self, async_client):
        """Test login with nonexistent email."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401


@pytest.mark.asyncio
class TestAuthMe:
    """Test GET /auth/me endpoint."""

    async def test_get_current_user_success(self, async_client, create_test_user):
        """Test getting current user info."""
        # Create a user and get their token
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        response = await async_client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user["email"]
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"

    async def test_get_current_user_no_token(self, async_client):
        """Test accessing /auth/me without token."""
        response = await async_client.get("/auth/me")

        assert response.status_code == 403  # HTTPBearer returns 403 when no token provided

    async def test_get_current_user_invalid_token(self, async_client):
        """Test accessing /auth/me with invalid token."""
        response = await async_client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
