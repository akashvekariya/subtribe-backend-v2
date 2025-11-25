"""
Unit tests for Pydantic schemas.

Tests validation rules, field constraints, and serialization.
"""

import pytest
from pydantic import ValidationError

from app.schemas.application import ApplicationCreate, ApplicationStatusUpdate
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.company import CompanyUpdate
from app.schemas.job import JobCreate, JobUpdate


class TestAuthSchemas:
    """Test authentication schemas."""

    def test_user_register_valid(self):
        """Test valid user registration data."""
        data = RegisterRequest(
            email="test@example.com",
            password="SecurePass123!",
            first_name="Test",
            last_name="User",
            company_code="ACME-x7k9p2",
        )
        assert data.email == "test@example.com"
        assert data.first_name == "Test"
        assert data.last_name == "User"
        assert data.company_code == "ACME-x7k9p2"

    def test_user_register_invalid_email(self):
        """Test registration with invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="not-an-email",
                password="SecurePass123!",
                first_name="Test",
                last_name="User",
                company_code="ACME-x7k9p2",
            )
        assert "email" in str(exc_info.value).lower()

    def test_user_login_valid(self):
        """Test valid login data."""
        data = LoginRequest(email="test@example.com", password="password123")
        assert data.email == "test@example.com"
        assert data.password == "password123"


class TestCompanySchemas:
    """Test company schemas."""

    def test_company_update_valid(self):
        """Test valid company update data."""
        data = CompanyUpdate(
            name="Updated Name",
            tagline="New tagline",
            website_url="https://example.com",
        )
        assert data.name == "Updated Name"
        assert data.website_url == "https://example.com"

    def test_company_update_invalid_url(self):
        """Test company update with invalid URL."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyUpdate(website_url="not-a-url")
        assert "url" in str(exc_info.value).lower()

    def test_company_update_partial(self):
        """Test partial company update (all fields optional)."""
        data = CompanyUpdate(tagline="Just updating tagline")
        assert data.tagline == "Just updating tagline"
        assert data.name is None
        assert data.website_url is None


class TestJobSchemas:
    """Test job schemas."""

    def test_job_create_valid(self):
        """Test valid job creation data."""
        data = JobCreate(
            title="Software Engineer",
            description="Build amazing products",
            department="Engineering",
            position_type="full_time",
            location_type="onsite",
            location_city="Mumbai",
            location_country="India",
        )
        assert data.title == "Software Engineer"
        assert data.position_type == "full_time"

    def test_job_create_with_optional_fields(self):
        """Test job creation with optional fields."""
        data = JobCreate(
            title="Product Manager",
            description="Lead product initiatives",
            department="Product",
            position_type="contract",
            location_type="remote",
            location_country="India",
            experience_level="Senior",
            salary_min=1500000,
            salary_max=2500000,
        )
        assert data.experience_level == "Senior"
        assert data.salary_min == 1500000

    def test_job_update_status(self):
        """Test job status update."""
        data = JobUpdate(status="active")
        assert data.status == "active"

    def test_job_update_invalid_status(self):
        """Test job update with invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            JobUpdate(status="invalid_status")
        assert "status" in str(exc_info.value).lower()


class TestApplicationSchemas:
    """Test application schemas."""

    def test_application_create_valid(self):
        """Test valid application creation data."""
        data = ApplicationCreate(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+919876543210",
            current_ctc=1200000,
            expected_ctc=1500000,
            notice_period_days=30,
        )
        assert data.first_name == "John"
        assert data.last_name == "Doe"

    def test_application_create_invalid_email(self):
        """Test application with invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            ApplicationCreate(
                first_name="John",
                last_name="Doe",
                email="invalid-email",
                phone="+919876543210",
                current_ctc=1200000,
                expected_ctc=1500000,
                notice_period_days=30,
            )
        assert "email" in str(exc_info.value).lower()

    def test_application_status_update(self):
        """Test application status update."""
        data = ApplicationStatusUpdate(status="screening", notes="Strong candidate")
        assert data.status == "screening"
        assert data.notes == "Strong candidate"

    def test_application_status_update_invalid_status(self):
        """Test application update with invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            ApplicationStatusUpdate(status="invalid_status", notes="Some notes")
        assert "status" in str(exc_info.value).lower()

    def test_application_status_update_without_notes(self):
        """Test application update allows optional notes."""
        # Notes are now optional - both None and empty string should work
        data = ApplicationStatusUpdate(status="screening", notes=None)
        assert data.status == "screening"
        assert data.notes is None

        # Empty string gets cleaned to None
        data2 = ApplicationStatusUpdate(status="screening", notes="")
        assert data2.notes is None

        # Can omit notes entirely
        data3 = ApplicationStatusUpdate(status="screening")
        assert data3.notes is None
