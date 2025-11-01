"""Database connection and session management."""

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# SQLAlchemy 2.0 Base
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Async engine (only create if using async driver)
if "+asyncpg" in settings.database_url or "+psycopg" in settings.database_url:
    # For asyncpg with PgBouncer: use unique prepared statement names to avoid collisions
    # Solution from: https://github.com/MagicStack/asyncpg/issues/1058#issuecomment-1913635739
    connect_args = {}
    if "+asyncpg" in settings.database_url:
        connect_args = {
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }

    engine = create_async_engine(
        settings.database_url,
        echo=False,  # Don't log SQL queries (use our logging middleware instead)
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
    )

    # Session factory
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
    )
else:
    # For Alembic migrations (uses sync driver)
    engine = None
    AsyncSessionLocal = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
