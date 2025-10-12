"""Integration tests for company endpoints."""

import pytest


@pytest.mark.asyncio
class TestGetCompany:
    """Test GET /companies/{id} endpoint."""

    async def test_get_company_success(self, async_client, create_test_user, test_company):
        """Test getting company details."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Get company
        response = await async_client.get(
            f"/companies/{test_company.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_company.id)
        assert "invite_code" in data

    async def test_get_company_unauthorized(self, async_client, test_company):
        """Test getting company without auth."""
        response = await async_client.get(f"/companies/{test_company.id}")

        assert response.status_code == 403

    async def test_get_company_not_found(self, async_client, create_test_user):
        """Test getting non-existent company."""
        from uuid import uuid4

        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        response = await async_client.get(
            f"/companies/{uuid4()}",
            headers=auth_headers,
        )

        # Should return 403 because company_id doesn't match user's company
        assert response.status_code == 403


@pytest.mark.asyncio
class TestUpdateCompany:
    """Test PATCH /companies/{id} endpoint."""

    async def test_update_company_success(self, async_client, create_test_user, test_company):
        """Test updating company profile."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Update company
        response = await async_client.patch(
            f"/companies/{test_company.id}",
            headers=auth_headers,
            json={
                "name": "Updated Company Name",
                "tagline": "We hire the best!",
                "about": "A great company to work for.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Company Name"
        assert data["tagline"] == "We hire the best!"

    async def test_update_company_partial(self, async_client, create_test_user, test_company):
        """Test partial update of company."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Partial update
        response = await async_client.patch(
            f"/companies/{test_company.id}",
            headers=auth_headers,
            json={"tagline": "New tagline only"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tagline"] == "New tagline only"

    async def test_update_company_invalid_url(self, async_client, create_test_user, test_company):
        """Test updating company with invalid URL."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Try invalid URL
        response = await async_client.patch(
            f"/companies/{test_company.id}",
            headers=auth_headers,
            json={"website_url": "not-a-valid-url"},
        )

        assert response.status_code == 422  # Validation error

    async def test_update_company_unauthorized(self, async_client, test_company):
        """Test updating company without auth."""
        response = await async_client.patch(
            f"/companies/{test_company.id}",
            json={"name": "Hacked Name"},
        )

        assert response.status_code == 403
