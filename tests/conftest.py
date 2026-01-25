"""
Pytest configuration and shared fixtures for all tests.

IMPORTANT: This uses pytest-asyncio in AUTO mode (see pytest.ini).
Each test gets its own event loop and database transaction.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job
from app.models.user import User

# Test company details
TEST_COMPANY_ID = "3b0fc8bf-f923-40d5-a992-5a2c5f29b52a"
TEST_COMPANY_INVITE_CODE = "FIRSTINVITE"


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

# Single test engine shared across all tests (NullPool = fresh connection per test)
_test_engine = None


def get_test_engine():
    """Get or create the shared test engine with NullPool."""
    global _test_engine
    if _test_engine is None:
        _test_engine = create_async_engine(
            str(settings.database_url),
            poolclass=NullPool,  # No connection pooling = new connection per test
            echo=False,
            connect_args={
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )
    return _test_engine


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an isolated database session for each test.

    Uses shared engine with NullPool (creates fresh connection per test).
    Transaction rollback ensures test isolation.
    Explicit cleanup prevents connection accumulation.
    """
    import gc

    engine = get_test_engine()
    connection = None
    transaction = None
    session = None

    try:
        # Create session factory
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create connection and begin transaction
        connection = await engine.connect()
        transaction = await connection.begin()
        session = async_session_factory(bind=connection)

        yield session

    finally:
        # CRITICAL: Explicit cleanup in reverse order to prevent leaks
        if session:
            try:
                await session.close()
            except Exception:
                pass

        if transaction:
            try:
                await transaction.rollback()
            except Exception:
                pass

        if connection:
            try:
                await connection.close()
            except Exception:
                pass

        # Force garbage collection to release resources
        gc.collect()


# ============================================================================
# TEST CLIENT FIXTURES
# ============================================================================


@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    Synchronous test client for simple tests.

    WARNING: Use async_client for tests that need database access.
    """
    return TestClient(app)


@pytest_asyncio.fixture(scope="function")
async def async_client(test_db):
    """
    Async test client for integration tests with database access.

    CRITICAL: Replaces app's engine with test engine to prevent dual connections.
    Without this, both app.engine and test_engine create connections = exhausted pool.
    """
    # Import app's database module
    from app import database as app_db

    # CRITICAL: Replace app's engine with test engine to prevent connection exhaustion
    original_engine = app_db.engine
    test_engine = get_test_engine()
    app_db.engine = test_engine

    # Override get_db to use test database session
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    # Create client
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    try:
        yield client
    finally:
        # Cleanup
        await client.aclose()
        app.dependency_overrides.clear()

        # Restore original engine
        app_db.engine = original_engine


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================


@pytest.fixture
def test_company():
    """Returns test company data without database access."""
    from types import SimpleNamespace
    from uuid import UUID

    return SimpleNamespace(
        id=UUID(TEST_COMPANY_ID),
        invite_code=TEST_COMPANY_INVITE_CODE,
        name="Subtribe",
        slug="subtribe",
    )


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """
    Create a test user in the database.

    For unit tests only. Integration tests should create users via API.
    """
    from uuid import UUID

    from app.routers.auth import hash_password

    user = User(
        email="test@example.com",
        password_hash=hash_password("password123"),
        first_name="Test",
        last_name="User",
        company_id=UUID(TEST_COMPANY_ID),
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(test_db: AsyncSession) -> User:
    """Create a second test user (for status change tracking)."""
    from uuid import UUID

    from app.routers.auth import hash_password

    user = User(
        email="user2@example.com",
        password_hash=hash_password("password123"),
        first_name="Second",
        last_name="User",
        company_id=UUID(TEST_COMPANY_ID),
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers() -> dict:
    """Create authentication headers with JWT token for test company."""
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from jose import jwt

    payload = {
        "sub": str(uuid4()),
        "company_id": TEST_COMPANY_ID,
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_get_current_user(test_user: User, test_company: Company):
    """Override get_current_user dependency to skip auth validation."""

    async def _mock_get_current_user():
        return {
            "user_id": str(test_user.id),
            "company_id": str(test_company.id),
            "email": test_user.email,
        }

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    yield
    app.dependency_overrides.clear()


# ============================================================================
# DATA FIXTURES (For Unit Tests Only)
# ============================================================================


@pytest_asyncio.fixture
async def test_job(test_db: AsyncSession, test_user: User) -> Job:
    """Create a test job via database. For unit tests only."""
    import time
    from uuid import UUID

    job = Job(
        title="Software Engineer",
        description="Test job description for an amazing opportunity",
        department="Engineering",
        position_type="full_time",
        location_type="hybrid",
        location_city="Mumbai",
        location_country="India",
        company_id=UUID(TEST_COMPANY_ID),
        created_by=test_user.id,
        status="active",
        slug=f"software-engineer-{int(time.time())}",
    )
    test_db.add(job)
    await test_db.commit()
    await test_db.refresh(job)
    return job


@pytest_asyncio.fixture
async def test_application(test_db: AsyncSession, test_job: Job) -> Application:
    """Create a test application via database. For unit tests only."""
    from uuid import UUID

    application = Application(
        job_id=test_job.id,
        company_id=UUID(TEST_COMPANY_ID),
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+919876543210",
        current_ctc=1200000,
        expected_ctc=1500000,
        notice_period_days=30,
        resume_url="gs://test-bucket/test-resume.pdf",
        status="applied",
    )
    test_db.add(application)
    await test_db.commit()
    await test_db.refresh(application)
    return application


# ============================================================================
# MOCK FIXTURES (External Services)
# ============================================================================


@pytest.fixture
def mock_storage_service():
    """Mock GCS storage service to avoid actual GCS calls."""
    mock = MagicMock()
    mock.upload_resume = AsyncMock(return_value="gs://test-bucket/test-resume.pdf")
    mock.get_signed_url = AsyncMock(return_value="https://storage.googleapis.com/signed-url")
    return mock


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client to avoid actual auth calls."""
    mock = MagicMock()
    mock.auth.sign_up.return_value.user = MagicMock(id="test-uid-123", email="test@example.com")
    mock.auth.sign_in_with_password.return_value.user = MagicMock(
        id="test-uid-123", email="test@example.com"
    )
    mock.auth.sign_in_with_password.return_value.session = MagicMock(
        access_token="test-access-token"
    )
    return mock


# ============================================================================
# INTEGRATION TEST HELPERS (Create data via API)
# ============================================================================


@pytest_asyncio.fixture
async def create_test_user(async_client, test_company):
    """Async helper to create users via /auth/register API."""
    import time

    async def _create_user(email=None):
        if email is None:
            email = f"test_{int(time.time() * 1000)}@example.com"

        response = await async_client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "TestPass123!",
                "first_name": "Test",
                "last_name": "User",
                "company_code": test_company.invite_code,
            },
        )

        if response.status_code != 201:
            raise ValueError(f"Failed to create user: {response.json()}")

        data = response.json()
        return {
            "email": email,
            "token": data["access_token"],
            "user": data["user"],
        }

    return _create_user


@pytest_asyncio.fixture
async def create_test_job(async_client, create_test_user):
    """Async helper to create jobs via /jobs API."""

    async def _create_job(auth_headers=None, **kwargs):
        if auth_headers is None:
            user = await create_test_user()
            auth_headers = {"Authorization": f"Bearer {user['token']}"}

        # Default job data
        job_data = {
            "title": "Test Job",
            "description": "Test job description for an amazing opportunity",
            "department": "Engineering",
            "position_type": "full_time",
            "location_type": "hybrid",
            "location_city": "Mumbai",
            "location_country": "India",
            "status": "active",
        }

        # Override with kwargs
        job_data.update(kwargs)

        response = await async_client.post(
            "/jobs",
            headers=auth_headers,
            json=job_data,
        )

        if response.status_code != 201:
            raise ValueError(f"Failed to create job: {response.json()}")

        return response.json()

    return _create_job


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def sample_pdf_file():
    """Return path to sample PDF file for testing."""
    return os.path.join(os.path.dirname(__file__), "data", "test.pdf")
