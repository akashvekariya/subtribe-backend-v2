"""
Unit tests for SQLAlchemy models.

Tests model creation, relationships, and validation.
Uses test database (not mocked).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.company import Company
from app.models.job import Job
from app.models.status_history import ApplicationStatusHistory
from app.models.user import User


@pytest.mark.asyncio
class TestCompanyModel:
    """Test Company model."""

    async def test_create_company(self, test_db: AsyncSession):
        """Test creating a company."""
        company = Company(
            name="Acme Corp",
            slug="acme-corp",
            invite_code="ACME-x7k9p2",
        )
        test_db.add(company)
        await test_db.commit()
        await test_db.refresh(company)

        assert company.id is not None
        assert company.name == "Acme Corp"
        assert company.slug == "acme-corp"
        assert company.invite_code == "ACME-x7k9p2"
        assert company.created_at is not None

    async def test_company_with_optional_fields(self, test_db: AsyncSession):
        """Test company with logo, tagline, etc."""
        company = Company(
            name="Tech Inc",
            slug="tech-inc",
            invite_code="TECH-abc123",
            logo_url="https://example.com/logo.png",
            tagline="Innovation at scale",
            about="We build amazing products",
            website_url="https://tech-inc.com",
        )
        test_db.add(company)
        await test_db.commit()
        await test_db.refresh(company)

        assert company.logo_url == "https://example.com/logo.png"
        assert company.tagline == "Innovation at scale"
        assert company.about == "We build amazing products"
        assert company.website_url == "https://tech-inc.com"


@pytest.mark.asyncio
class TestUserModel:
    """Test User model."""

    async def test_create_user(self, test_db: AsyncSession):
        """Test creating a user."""
        from uuid import UUID

        from tests.conftest import TEST_COMPANY_ID

        user = User(
            email="john@example.com",
            password_hash="hashed_password_here",
            first_name="John",
            last_name="Doe",
            company_id=UUID(TEST_COMPANY_ID),
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.id is not None
        assert user.email == "john@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.full_name == "John Doe"  # Computed property
        assert user.company_id == UUID(TEST_COMPANY_ID)
        assert user.created_at is not None

    async def test_user_company_relationship(self, test_db: AsyncSession, test_user: User):
        """Test User.company relationship."""
        from uuid import UUID

        from tests.conftest import TEST_COMPANY_ID

        await test_db.refresh(test_user, ["company"])
        assert test_user.company.id == UUID(TEST_COMPANY_ID)
        assert test_user.company.name is not None  # Just verify relationship works


@pytest.mark.asyncio
class TestJobModel:
    """Test Job model."""

    async def test_create_job(self, test_db: AsyncSession, test_user: User):
        """Test creating a job."""
        import time
        from uuid import UUID

        from tests.conftest import TEST_COMPANY_ID

        job = Job(
            title="Backend Engineer",
            department="Engineering",
            position_type="full_time",
            location_type="onsite",
            location_city="Bangalore",
            location_country="India",
            description="Build scalable systems",
            company_id=UUID(TEST_COMPANY_ID),
            created_by=test_user.id,
            status="draft",
            slug=f"backend-engineer-{int(time.time())}",
        )
        test_db.add(job)
        await test_db.commit()
        await test_db.refresh(job)

        assert job.id is not None
        assert job.title == "Backend Engineer"
        assert job.status == "draft"
        assert job.slug is not None
        assert job.created_at is not None

    async def test_job_relationships(self, test_db: AsyncSession, test_job: Job):
        """Test Job.company and Job.creator relationships."""
        await test_db.refresh(test_job, ["company", "creator"])
        assert test_job.company is not None
        assert test_job.creator is not None
        assert test_job.creator.full_name == "Test User"


@pytest.mark.asyncio
class TestApplicationModel:
    """Test Application model."""

    async def test_create_application(self, test_db: AsyncSession, test_job: Job):
        """Test creating an application."""
        from uuid import UUID

        from tests.conftest import TEST_COMPANY_ID

        application = Application(
            job_id=test_job.id,
            company_id=UUID(TEST_COMPANY_ID),
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+919876543210",
            current_ctc=800000,
            expected_ctc=1200000,
            notice_period_days=60,
            resume_url="gs://bucket/resume.pdf",
            status="applied",
        )
        test_db.add(application)
        await test_db.commit()
        await test_db.refresh(application)

        assert application.id is not None
        assert application.first_name == "Jane"
        assert application.last_name == "Smith"
        assert application.status == "applied"
        assert application.applied_at is not None

    async def test_application_job_relationship(
        self, test_db: AsyncSession, test_application: Application, test_job: Job
    ):
        """Test Application.job relationship."""
        await test_db.refresh(test_application, ["job"])
        assert test_application.job.id == test_job.id
        assert test_application.job.title == test_job.title


@pytest.mark.asyncio
class TestStatusHistoryModel:
    """Test ApplicationStatusHistory model."""

    async def test_create_status_history(
        self, test_db: AsyncSession, test_application: Application, test_user: User
    ):
        """Test creating a status history entry."""
        history = ApplicationStatusHistory(
            application_id=test_application.id,
            from_status="applied",
            to_status="screening",
            changed_by=test_user.id,
            notes="Strong technical skills",
        )
        test_db.add(history)
        await test_db.commit()
        await test_db.refresh(history)

        assert history.id is not None
        assert history.to_status == "screening"
        assert history.from_status == "applied"
        assert history.notes == "Strong technical skills"
        assert history.created_at is not None

    async def test_status_history_relationships(
        self, test_db: AsyncSession, test_application: Application, test_user: User
    ):
        """Test StatusHistory relationships."""
        history = ApplicationStatusHistory(
            application_id=test_application.id,
            from_status="applied",
            to_status="interviewing",
            changed_by=test_user.id,
        )
        test_db.add(history)
        await test_db.commit()
        await test_db.refresh(history, ["application", "changed_by_user"])

        assert history.application.id == test_application.id
        assert history.changed_by_user.id == test_user.id
