"""
End-to-end tests for complete user flows.

Tests the full journey:
1. User registration
2. Company setup
3. Job creation
4. Public job view
5. Application submission
6. Application management
7. Status changes with history

Can be run against local or staging environments via E2E_BASE_URL.
"""

import os
import time
from typing import Optional

import httpx
import pytest

from tests.e2e.config import E2E_CONFIG, get_base_url, is_local_environment


class E2ETestContext:
    """Shared context for E2E tests."""

    def __init__(self):
        self.base_url = get_base_url()
        self.access_token: str | None = None
        self.company_id: str | None = None
        self.user_id: str | None = None
        self.job_id: str | None = None
        self.job_slug: str | None = None
        self.application_id: str | None = None

    def get_auth_headers(self) -> dict:
        """Get authentication headers."""
        if not self.access_token:
            raise ValueError("Not authenticated. Run login flow first.")
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest.fixture(scope="module")
def e2e_context():
    """Shared context for all E2E tests in this module."""
    return E2ETestContext()


@pytest.fixture(scope="module")
def http_client():
    """HTTP client for E2E tests."""
    return httpx.Client(timeout=E2E_CONFIG["request_timeout"])


@pytest.mark.e2e
class TestCompleteUserJourney:
    """Test complete user journey from registration to hiring."""

    def test_01_register_or_login(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 1: Register new user or login if exists."""
        # Generate unique email for local tests
        if is_local_environment():
            timestamp = int(time.time())
            test_email = f"e2e_user_{timestamp}@example.com"

            # Try registration
            response = http_client.post(
                f"{e2e_context.base_url}/auth/register",
                json={
                    "email": test_email,
                    "password": "E2ETestPass123!",
                    "first_name": "E2E",
                    "last_name": "TestUser",
                    "company_code": E2E_CONFIG["test_company_code"],
                },
            )

            if response.status_code == 201:
                # Registration successful
                data = response.json()
                e2e_context.access_token = data["access_token"]
                e2e_context.company_id = data["user"]["company"]["id"]
                e2e_context.user_id = data["user"]["id"]
                print(f"✅ Registered new user: {test_email}")
            else:
                pytest.fail(f"Registration failed: {response.text}")
        else:
            # For staging/production, use existing credentials
            response = http_client.post(
                f"{e2e_context.base_url}/auth/login",
                json={
                    "email": E2E_CONFIG["test_email"],
                    "password": E2E_CONFIG["test_password"],
                },
            )

            assert response.status_code == 200, f"Login failed: {response.text}"
            data = response.json()
            e2e_context.access_token = data["access_token"]
            e2e_context.company_id = data["user"]["company"]["id"]
            e2e_context.user_id = data["user"]["id"]
            print(f"✅ Logged in: {E2E_CONFIG['test_email']}")

        # Verify we can access /auth/me
        response = http_client.get(
            f"{e2e_context.base_url}/auth/me",
            headers=e2e_context.get_auth_headers(),
        )
        assert response.status_code == 200
        print("✅ Authentication verified")

    def test_02_update_company_profile(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Step 2: Update company profile."""
        response = http_client.patch(
            f"{e2e_context.base_url}/companies/{e2e_context.company_id}",
            headers=e2e_context.get_auth_headers(),
            json={
                "tagline": "E2E Test Company",
                "about": "This is an automated E2E test company",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tagline"] == "E2E Test Company"
        print("✅ Company profile updated")

    def test_03_create_job(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 3: Create a new job posting."""
        timestamp = int(time.time())
        response = http_client.post(
            f"{e2e_context.base_url}/jobs",
            headers=e2e_context.get_auth_headers(),
            json={
                "title": f"E2E Test Job {timestamp}",
                "description": "This is an E2E test job posting. Must be willing to test.",
                "department": "Engineering",
                "position_type": "full_time",
                "location_type": "hybrid",
                "location_city": "Mumbai",
                "location_country": "India",
                "experience_level": "Entry",
                "salary_min": 500000,
                "salary_max": 1000000,
                "salary_currency": "INR",
            },
        )

        assert response.status_code == 201
        data = response.json()
        e2e_context.job_id = data["id"]
        e2e_context.job_slug = data["slug"]
        assert data["status"] == "draft"
        print(f"✅ Job created: {e2e_context.job_slug}")

    def test_04_publish_job(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 4: Publish the job (draft -> active)."""
        response = http_client.patch(
            f"{e2e_context.base_url}/jobs/{e2e_context.job_id}",
            headers=e2e_context.get_auth_headers(),
            json={"status": "active"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["published_at"] is not None
        print("✅ Job published")

    def test_05_view_public_job_page(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 5: View public job page (as candidate)."""
        response = http_client.get(f"{e2e_context.base_url}/public/jobs/{e2e_context.job_slug}")

        assert response.status_code == 200
        data = response.json()
        # Response is flat PublicJobResponse with nested company
        assert data["title"] is not None
        assert "company" in data
        assert data["company"]["name"] is not None
        print("✅ Public job page accessible")

    def test_06_submit_application(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 6: Submit application with resume."""
        # Create a fake PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"

        timestamp = int(time.time())
        files = {"resume": ("resume.pdf", pdf_content, "application/pdf")}
        data = {
            "first_name": "E2E",
            "last_name": "Candidate",
            "email": f"candidate_{timestamp}@example.com",
            "phone": "+919876543210",
            "current_ctc": "800000",
            "expected_ctc": "1200000",
            "notice_period_days": "30",
        }

        response = http_client.post(
            f"{e2e_context.base_url}/public/jobs/{e2e_context.job_slug}/apply",
            data=data,
            files=files,
        )

        assert response.status_code == 201
        app_data = response.json()
        e2e_context.application_id = app_data["id"]
        print(f"✅ Application submitted: {e2e_context.application_id}")

    def test_07_view_application_list(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 7: View applications for the job."""
        response = http_client.get(
            f"{e2e_context.base_url}/jobs/{e2e_context.job_id}/applications",
            headers=e2e_context.get_auth_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        # Response structure is {"data": [...], "pagination": {...}}
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) > 0

        # Verify our application is in the list
        app_ids = [app["id"] for app in data["data"]]
        assert e2e_context.application_id in app_ids
        print("✅ Application appears in list")

    def test_08_view_application_details(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Step 8: View single application details."""
        response = http_client.get(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}",
            headers=e2e_context.get_auth_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == e2e_context.application_id
        assert data["first_name"] == "E2E"
        assert data["last_name"] == "Candidate"
        print("✅ Application details retrieved")

    def test_09_get_resume_view_url(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 9: Get signed URL to view resume."""
        response = http_client.get(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}/resume/view",
            headers=e2e_context.get_auth_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert data["url"].startswith("http")
        print("✅ Resume view URL generated")

    def test_10_change_status_to_screening(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Step 10: Change application status to screening."""
        response = http_client.patch(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}",
            headers=e2e_context.get_auth_headers(),
            json={
                "status": "screening",
                "notes": "Strong technical background",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "screening"
        print("✅ Status changed to screening")

    def test_11_change_status_to_interviewing(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Step 11: Change status to interviewing."""
        response = http_client.patch(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}",
            headers=e2e_context.get_auth_headers(),
            json={
                "status": "interviewing",
                "notes": "Scheduled for technical round",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "interviewing"
        print("✅ Status changed to interviewing")

    def test_12_view_status_history(self, http_client: httpx.Client, e2e_context: E2ETestContext):
        """Step 12: View complete status history."""
        response = http_client.get(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}/history",
            headers=e2e_context.get_auth_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        # Response structure is {"data": [...]}
        assert "data" in data

        # Should have: applied, screening, interviewing (changed from shortlisted to screening)
        assert len(data["data"]) >= 3

        statuses = [h["to_status"] for h in data["data"]]
        assert "applied" in statuses
        assert "screening" in statuses or "interviewing" in statuses

        print(f"✅ Status history complete: {statuses}")

    def test_13_change_status_to_hired(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Step 13: Final status change to hired."""
        response = http_client.patch(
            f"{e2e_context.base_url}/applications/{e2e_context.application_id}",
            headers=e2e_context.get_auth_headers(),
            json={
                "status": "hired",
                "notes": "Welcome to the team!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "hired"
        print("✅ Status changed to hired - Journey complete! 🎉")


@pytest.mark.e2e
class TestEdgeCases:
    """Test edge cases and error scenarios in E2E environment."""

    def test_duplicate_application_rejected(
        self, http_client: httpx.Client, e2e_context: E2ETestContext
    ):
        """Test that duplicate applications are rejected."""
        if not e2e_context.job_slug:
            pytest.skip("Requires job from previous tests")

        pdf_content = b"%PDF-1.4\n%%EOF"
        duplicate_email = "duplicate_test@example.com"

        # First application
        response1 = http_client.post(
            f"{e2e_context.base_url}/public/jobs/{e2e_context.job_slug}/apply",
            data={
                "first_name": "First",
                "last_name": "Application",
                "email": duplicate_email,
                "phone": "+919876543210",
                "current_ctc": "800000",
                "expected_ctc": "1200000",
                "notice_period_days": "30",
            },
            files={"resume": ("resume.pdf", pdf_content, "application/pdf")},
        )

        # Second application with same email
        response2 = http_client.post(
            f"{e2e_context.base_url}/public/jobs/{e2e_context.job_slug}/apply",
            data={
                "first_name": "Second",
                "last_name": "Application",
                "email": duplicate_email,
                "phone": "+919999999999",
                "current_ctc": "1000000",
                "expected_ctc": "1500000",
                "notice_period_days": "60",
            },
            files={"resume": ("resume2.pdf", pdf_content, "application/pdf")},
        )

        # First should succeed, second should fail
        assert response1.status_code == 201
        assert response2.status_code == 409
        print("✅ Duplicate application correctly rejected")
