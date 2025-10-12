"""Integration tests for application endpoints."""

import io

import pytest


@pytest.mark.asyncio
class TestSubmitApplication:
    """Test POST /public/jobs/{slug}/apply endpoint."""

    async def test_submit_application_success(
        self, async_client, create_test_user, create_test_job
    ):
        """Test submitting application with resume."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create PDF file
        pdf_content = b"%PDF-1.4\n%Test PDF content\n%%EOF"
        pdf_file = io.BytesIO(pdf_content)

        # Submit application
        response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "phone": "+919876543210",
                "current_ctc": "800000",
                "expected_ctc": "1200000",
                "notice_period_days": "60",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["message"] == "Application submitted successfully"

    async def test_submit_application_duplicate_email(
        self, async_client, create_test_user, create_test_job
    ):
        """Test duplicate application rejection."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create PDF file
        pdf_content = b"%PDF-1.4\n%Test PDF content\n%%EOF"

        # Submit first application
        pdf_file1 = io.BytesIO(pdf_content)
        response1 = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "duplicate@example.com",
                "phone": "+919876543210",
            },
            files={"resume": ("resume.pdf", pdf_file1, "application/pdf")},
        )
        assert response1.status_code == 201

        # Try to submit again with same email
        pdf_file2 = io.BytesIO(pdf_content)
        response2 = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Smith",
                "email": "duplicate@example.com",
                "phone": "+919876543211",
            },
            files={"resume": ("resume2.pdf", pdf_file2, "application/pdf")},
        )

        assert response2.status_code == 409
        assert "already applied" in response2.json()["error"]["message"].lower()

    async def test_submit_application_invalid_file_type(
        self, async_client, create_test_user, create_test_job
    ):
        """Test invalid file type rejection."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create txt file
        txt_file = io.BytesIO(b"This is a text file")

        response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.txt", txt_file, "text/plain")},
        )

        assert response.status_code == 400
        assert "pdf" in response.json()["error"]["message"].lower()

    async def test_submit_application_job_not_found(self, async_client):
        """Test application submission to non-existent job."""
        pdf_content = b"%PDF-1.4\n%Test PDF content\n%%EOF"
        pdf_file = io.BytesIO(pdf_content)

        response = await async_client.post(
            "/public/jobs/nonexistent-job-slug/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestListApplications:
    """Test GET /jobs/{job_id}/applications endpoint."""

    async def test_list_applications_success(self, async_client, create_test_user, create_test_job):
        """Test listing applications for a job."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create 2 applications
        for i in range(2):
            pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
            await async_client.post(
                f"/public/jobs/{job['slug']}/apply",
                data={
                    "first_name": f"Candidate{i}",
                    "last_name": "Doe",
                    "email": f"candidate{i}@example.com",
                },
                files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
            )

        # List applications
        response = await async_client.get(
            f"/jobs/{job['id']}/applications",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 2

    async def test_list_applications_unauthorized(
        self, async_client, create_test_user, create_test_job
    ):
        """Test listing applications without auth."""
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers)

        response = await async_client.get(f"/jobs/{job['id']}/applications")

        assert response.status_code == 403


@pytest.mark.asyncio
class TestGetApplication:
    """Test GET /applications/{id} endpoint."""

    async def test_get_application_success(self, async_client, create_test_user, create_test_job):
        """Test getting application details."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Get application details
        response = await async_client.get(
            f"/applications/{app_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "job" in data

    async def test_get_application_not_found(self, async_client, create_test_user):
        """Test getting non-existent application."""
        from uuid import uuid4

        # Create user
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}

        response = await async_client.get(
            f"/applications/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestUpdateApplication:
    """Test PATCH /applications/{id} endpoint."""

    async def test_update_application_status(self, async_client, create_test_user, create_test_job):
        """Test updating application status."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Update status
        response = await async_client.patch(
            f"/applications/{app_id}",
            headers=auth_headers,
            json={
                "status": "screening",
                "notes": "Initial screening passed",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "screening"

    async def test_update_application_creates_history(
        self, async_client, create_test_user, create_test_job
    ):
        """Test that status update creates history entry."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Update status
        await async_client.patch(
            f"/applications/{app_id}",
            headers=auth_headers,
            json={
                "status": "screening",
                "notes": "Initial screening passed",
            },
        )

        # Check history
        history_response = await async_client.get(
            f"/applications/{app_id}/history",
            headers=auth_headers,
        )

        assert history_response.status_code == 200
        history = history_response.json()["data"]
        assert len(history) >= 2  # applied + screening
        assert history[0]["to_status"] == "screening"


@pytest.mark.asyncio
class TestResumeAccess:
    """Test resume view/download endpoints."""

    async def test_get_resume_view_url(self, async_client, create_test_user, create_test_job):
        """Test getting resume view URL."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Get resume view URL
        response = await async_client.get(
            f"/applications/{app_id}/resume/view",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "filename" in data

    async def test_get_resume_download_url(self, async_client, create_test_user, create_test_job):
        """Test getting resume download URL."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Get resume download URL
        response = await async_client.get(
            f"/applications/{app_id}/resume/download",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "filename" in data

    async def test_resume_access_unauthorized(
        self, async_client, create_test_user, create_test_job
    ):
        """Test resume access without auth."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        response = await async_client.get(f"/applications/{app_id}/resume/view")

        assert response.status_code == 403


@pytest.mark.asyncio
class TestApplicationHistory:
    """Test GET /applications/{id}/history endpoint."""

    async def test_get_application_history(self, async_client, create_test_user, create_test_job):
        """Test getting application status history."""
        # Create user and job
        user = await create_test_user()
        auth_headers = {"Authorization": f"Bearer {user['token']}"}
        job = await create_test_job(auth_headers=auth_headers)

        # Create application
        pdf_file = io.BytesIO(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        app_response = await async_client.post(
            f"/public/jobs/{job['slug']}/apply",
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            files={"resume": ("resume.pdf", pdf_file, "application/pdf")},
        )
        app_id = app_response.json()["id"]

        # Update status multiple times
        await async_client.patch(
            f"/applications/{app_id}",
            headers=auth_headers,
            json={"status": "screening", "notes": "Screening"},
        )
        await async_client.patch(
            f"/applications/{app_id}",
            headers=auth_headers,
            json={"status": "interviewing", "notes": "Interview scheduled"},
        )

        # Get history
        response = await async_client.get(
            f"/applications/{app_id}/history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # Should have 3 entries: applied, screening, interviewing
        assert len(data["data"]) == 3
