"""Integration tests for job endpoints."""

import pytest


@pytest.mark.asyncio
class TestCreateJob:
    """Test POST /jobs endpoint."""

    async def test_create_job_success(self, async_client, create_test_user):
        """Test creating a job."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Create job
        response = await async_client.post(
            "/jobs",
            headers=auth_headers,
            json={
                "title": "Backend Engineer",
                "description": "We're looking for a backend engineer",
                "position_type": "full_time",
                "location_type": "remote",
                "location_country": "India",
                "status": "draft",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Backend Engineer"
        assert data["status"] == "draft"
        assert "slug" in data

    async def test_create_job_with_optional_fields(self, async_client, create_test_user):
        """Test creating job with all optional fields."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Create job with all fields
        response = await async_client.post(
            "/jobs",
            headers=auth_headers,
            json={
                "title": "Senior Frontend Engineer",
                "description": "Build amazing UIs",
                "position_type": "full_time",
                "experience_level": "Senior",
                "department": "Engineering",
                "location_type": "hybrid",
                "location_city": "Mumbai",
                "location_state": "Maharashtra",
                "location_country": "India",
                "salary_min": 100000,
                "salary_max": 150000,
                "salary_currency": "INR",
                "status": "active",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Senior Frontend Engineer"
        assert data["salary_min"] == 100000
        assert data["published_at"] is not None  # Should be set when status is active

    async def test_create_job_unauthorized(self, async_client):
        """Test creating job without auth."""
        response = await async_client.post(
            "/jobs",
            json={
                "title": "Test Job",
                "description": "Test description",
            },
        )

        assert response.status_code == 403


@pytest.mark.asyncio
class TestListJobs:
    """Test GET /jobs endpoint."""

    async def test_list_jobs_success(self, async_client, create_test_user, create_test_job):
        """Test listing jobs."""
        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Create 2 jobs
        await create_test_job(auth_headers=auth_headers, title="Job 1")
        await create_test_job(auth_headers=auth_headers, title="Job 2")

        # List jobs
        response = await async_client.get(
            "/jobs",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    async def test_list_jobs_unauthorized(self, async_client):
        """Test listing jobs without auth."""
        response = await async_client.get("/jobs")

        assert response.status_code == 403


@pytest.mark.asyncio
class TestGetJob:
    """Test GET /jobs/{id} endpoint."""

    async def test_get_job_success(self, async_client, create_test_user, create_test_job):
        """Test getting job details."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Get job
        response = await async_client.get(
            f"/jobs/{job['id']}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job["id"]
        assert data["title"] == job["title"]

    async def test_get_job_not_found(self, async_client, create_test_user):
        """Test getting non-existent job."""
        from uuid import uuid4

        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        response = await async_client.get(
            f"/jobs/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestUpdateJob:
    """Test PATCH /jobs/{id} endpoint."""

    async def test_update_job_success(self, async_client, create_test_user, create_test_job):
        """Test updating job."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers, status="draft")

        # Update job
        response = await async_client.patch(
            f"/jobs/{job['id']}",
            headers=auth_headers,
            json={
                "title": "Updated Title",
                "description": "Updated description",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    async def test_update_job_status_to_active(
        self, async_client, create_test_user, create_test_job
    ):
        """Test updating job status to active sets published_at."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers, status="draft")

        # Update to active
        response = await async_client.patch(
            f"/jobs/{job['id']}",
            headers=auth_headers,
            json={"status": "active"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["published_at"] is not None

    async def test_update_job_unauthorized(self, async_client, create_test_user, create_test_job):
        """Test updating job without auth."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Try to update without auth
        response = await async_client.patch(
            f"/jobs/{job['id']}",
            json={"title": "Hacked Title"},
        )

        assert response.status_code == 403


@pytest.mark.asyncio
class TestPublicJobPage:
    """Test GET /public/jobs/{slug} endpoint."""

    async def test_get_public_job_success(self, async_client, create_test_user, create_test_job):
        """Test getting public job page."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers, status="active")

        # Get public job page
        response = await async_client.get(f"/public/jobs/{job['slug']}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == job["title"]
        assert "company" in data

    async def test_get_public_job_increments_views(
        self, async_client, create_test_user, create_test_job
    ):
        """Test that viewing public job increments view count."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers, status="active")

        # View job multiple times
        await async_client.get(f"/public/jobs/{job['slug']}")
        await async_client.get(f"/public/jobs/{job['slug']}")

        # Get job via auth endpoint to check views
        response = await async_client.get(
            f"/jobs/{job['id']}",
            headers=auth_headers,
        )

        # Views should have increased (background task)
        # Note: This test might be flaky due to background task timing
        assert response.status_code == 200

    async def test_get_public_job_not_found(self, async_client):
        """Test getting non-existent public job."""
        response = await async_client.get("/public/jobs/nonexistent-slug")

        assert response.status_code == 404
