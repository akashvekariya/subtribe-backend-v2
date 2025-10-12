"""Job endpoints - CRUD operations for job postings."""

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.models.application import Application
from app.models.job import Job
from app.schemas.application import (
    ApplicationListItem,
    ApplicationListResponse,
    PaginationMeta,
)
from app.schemas.job import (
    JobCreate,
    JobListItem,
    JobResponse,
    JobUpdate,
    PublicJobResponse,
)

router = APIRouter()
public_router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


def generate_slug(title: str, job_id: UUID) -> str:
    """
    Generate URL-friendly slug from job title and ID.

    Format: {sanitized-title}-{full-uuid}
    - Title is sanitized (lowercase, alphanumeric + hyphens only)
    - Full UUID ensures uniqueness (no collisions possible)
    - Example: "senior-backend-engineer-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    """
    # Sanitize title: lowercase, replace spaces with hyphens, remove special chars
    sanitized = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    sanitized = re.sub(r"[\s-]+", "-", sanitized).strip("-")

    # Limit title to 50 chars and append full UUID for uniqueness
    sanitized = sanitized[:50].rstrip("-")

    # Use full UUID to ensure uniqueness (no collisions)
    return f"{sanitized}-{str(job_id)}"


async def increment_view_count(db: AsyncSession, job_id: UUID):
    """Background task to increment job view count."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job:
        job.views_count += 1
        await db.commit()


# ============================================================================
# Authenticated Endpoints
# ============================================================================


@router.post("", response_model=JobResponse, status_code=201, tags=["Jobs"])
async def create_job(
    job_data: JobCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new job posting.

    - Defaults to 'draft' status
    - Auto-generates slug from title
    - Sets created_by from current user
    - Sets published_at when status is 'active'
    """
    # Generate UUID for the job first (so we can create the slug)
    from uuid import uuid4

    job_id = uuid4()

    # Generate slug using the job ID
    slug = generate_slug(job_data.title, job_id)

    # Create job instance with ID and slug
    job = Job(
        id=job_id,
        company_id=current_user["company_id"],
        created_by=current_user["user_id"],
        title=job_data.title,
        description=job_data.description,
        position_type=job_data.position_type,
        experience_level=job_data.experience_level,
        department=job_data.department,
        location_type=job_data.location_type,
        location_city=job_data.location_city,
        location_state=job_data.location_state,
        location_country=job_data.location_country,
        salary_min=job_data.salary_min,
        salary_max=job_data.salary_max,
        salary_currency=job_data.salary_currency,
        status=job_data.status,
        slug=slug,
    )

    # Set published_at if status is active
    if job_data.status == "active":
        job.published_at = datetime.now(timezone.utc)

    # Add to session and commit
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Load relationships
    stmt = (
        select(Job)
        .where(Job.id == job.id)
        .options(selectinload(Job.creator), selectinload(Job.company))
    )
    result = await db.execute(stmt)
    job_with_relations = result.scalar_one()

    return job_with_relations


@router.get("", response_model=list[JobListItem], tags=["Jobs"])
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all jobs for the current user's company.

    - Returns all jobs (draft, active, closed)
    - Multi-tenant filtered by company_id
    - No pagination for MVP (client-side filtering)
    """
    stmt = (
        select(Job)
        .where(Job.company_id == current_user["company_id"])
        .options(selectinload(Job.creator))
        .order_by(Job.created_at.desc())
    )

    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return jobs


@router.get("/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def get_job(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get job details by ID.

    - Multi-tenant: Only returns job if it belongs to user's company
    """
    stmt = (
        select(Job)
        .where(Job.id == job_id, Job.company_id == current_user["company_id"])
        .options(selectinload(Job.creator), selectinload(Job.company))
    )

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(message="Job not found", code="job_not_found")

    return job


@router.patch("/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def update_job(
    job_id: UUID,
    job_data: JobUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update job details.

    - Multi-tenant: Can only update jobs from user's company
    - Partial update: Only provided fields are updated
    - Sets published_at when status changes to 'active' (if not already set)
    """
    # Fetch job
    stmt = select(Job).where(Job.id == job_id, Job.company_id == current_user["company_id"])
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(message="Job not found", code="job_not_found")

    # Track status change
    old_status = job.status

    # Update fields (only if provided)
    update_data = job_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    # Set published_at if status changed to active and not already set
    if job.status == "active" and old_status != "active" and job.published_at is None:
        job.published_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(job)

    # Load relationships
    stmt = (
        select(Job)
        .where(Job.id == job.id)
        .options(selectinload(Job.creator), selectinload(Job.company))
    )
    result = await db.execute(stmt)
    job_with_relations = result.scalar_one()

    return job_with_relations


# ============================================================================
# Public Endpoints (No Authentication)
# ============================================================================


@public_router.get("/{slug}", response_model=PublicJobResponse, tags=["Public"])
async def get_public_job(
    slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public job posting by slug (for candidates).

    - No authentication required
    - Only returns active and closed jobs (never draft)
    - Includes company details (name, logo, website, tagline, about)
    - Increments view count in background
    """
    stmt = select(Job).where(Job.slug == slug).options(selectinload(Job.company))

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(message="Job not found", code="job_not_found")

    # Never show draft jobs on public page
    if job.status == "draft":
        raise NotFoundError(message="Job not found", code="job_not_found")

    # Increment view count in background
    background_tasks.add_task(increment_view_count, db, job.id)

    return job


@router.get("/{job_id}/applications", response_model=ApplicationListResponse, tags=["Applications"])
async def list_job_applications(
    job_id: UUID,
    status_filter: str | None = Query(
        None, alias="status", pattern="^(applied|screening|interviewing|offer|hired|rejected)$"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List applications for a job.

    - **job_id**: Job UUID
    - **status**: Filter by status (optional)
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 50)

    Returns paginated list of applications.
    """
    # 1. Verify job exists and belongs to user's company
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_user["company_id"])
    )
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(message="Job not found", code="job_not_found")

    # 2. Build query
    query = select(Application).where(Application.job_id == job_id)

    if status_filter:
        query = query.where(Application.status == status_filter)

    # Order by most recent first
    query = query.order_by(Application.applied_at.desc())

    # 3. Get total count
    count_query = select(func.count()).select_from(Application).where(Application.job_id == job_id)
    if status_filter:
        count_query = count_query.where(Application.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 4. Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # 5. Execute query
    result = await db.execute(query)
    applications = result.scalars().all()

    # 6. Build response
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_more = page < total_pages

    return ApplicationListResponse(
        data=[ApplicationListItem.model_validate(app) for app in applications],
        pagination=PaginationMeta(
            page=page, limit=limit, total=total, total_pages=total_pages, has_more=has_more
        ),
    )
