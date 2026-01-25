"""Job endpoints - CRUD operations for job postings."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.application import (
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationStatsResponse,
)
from app.schemas.common import PaginationMeta
from app.schemas.job import (
    CalibrationSaveRequest,
    JobActivityStats,
    JobApplicationsByStatus,
    JobApplicationStats,
    JobCalibrationResponse,
    JobCreate,
    JobListItem,
    JobListResponse,
    JobPipelineStats,
    JobQualityMetrics,
    JobResponse,
    JobStatsResponse,
    JobUpdate,
    JobViewStats,
    PublicJobResponse,
)
from app.services.evaluation import trigger_evaluation_for_job
from app.services.job_service import JobService

router = APIRouter()
public_router = APIRouter()


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
    service = JobService(db)
    return await service.create_job(
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        data=job_data,
    )


@router.get("", response_model=JobListResponse, tags=["Jobs"])
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all jobs for the current user's company with pagination.

    - Returns jobs (draft, active, closed)
    - Multi-tenant filtered by company_id
    - Paginated with metadata
    """
    service = JobService(db)
    jobs, total, pages = await service.list_jobs(
        company_id=current_user["company_id"],
        page=page,
        limit=limit,
    )

    return JobListResponse(
        data=[JobListItem(**job) for job in jobs],
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=pages,
            has_more=page < pages,
        ),
    )


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
    service = JobService(db)
    return await service.get_job(current_user["company_id"], job_id)


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
    service = JobService(db)
    return await service.update_job(current_user["company_id"], job_id, job_data)


@router.get("/{job_id}/stats", response_model=JobStatsResponse, tags=["Jobs"])
async def get_job_stats(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics for a specific job.

    Returns comprehensive stats including:
    - Application counts by status and time period
    - View statistics
    - Quality metrics (application rate, screening rate, etc.)
    - Activity metrics (latest application, days since published, etc.)
    - Pipeline conversion metrics
    """
    service = JobService(db)
    stats = await service.get_job_stats(current_user["company_id"], job_id)

    return JobStatsResponse(
        applications=JobApplicationStats(
            total=stats.total_applications,
            today=stats.today_applications,
            this_week=stats.week_applications,
            this_month=stats.month_applications,
            by_status=JobApplicationsByStatus(
                applied=stats.applied_count,
                screening=stats.screening_count,
                interviewing=stats.interviewing_count,
                offer=stats.offer_count,
                hired=stats.hired_count,
                rejected=stats.rejected_count,
            ),
        ),
        views=JobViewStats(total=stats.views_count),
        quality=JobQualityMetrics(
            application_rate=stats.application_rate,
            screening_rate=stats.screening_rate,
            interview_rate=stats.interview_rate,
            offer_rate=stats.offer_rate,
            hire_rate=stats.hire_rate,
        ),
        activity=JobActivityStats(
            latest_application_at=stats.latest_application_at,
            days_since_last_application=stats.days_since_last_application,
            days_since_published=stats.days_since_published,
            is_recently_active=stats.is_recently_active,
        ),
        pipeline=JobPipelineStats(
            conversion_rate=stats.conversion_rate,
            avg_time_to_hire_days=None,
        ),
        generated_at=stats.generated_at,
    )


@router.put("/{job_id}/calibration", response_model=JobCalibrationResponse, tags=["Jobs"])
async def save_job_calibration(
    job_id: UUID,
    calibration_data: CalibrationSaveRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save calibration results for a job.

    - Multi-tenant: Can only save calibration for jobs from user's company
    - Stores calibration_summary, evaluation_framework, and sets calibrated_at
    """
    service = JobService(db)
    job = await service.save_calibration(
        current_user["company_id"], job_id, calibration_data
    )

    # Auto-trigger evaluation for existing unevaluated applications
    triggered_count = await trigger_evaluation_for_job(
        db=db,
        job_id=job_id,
        triggered_by=UUID(current_user["user_id"]),
    )

    message = "Calibration saved successfully"
    if triggered_count > 0:
        message += f". Started evaluation for {triggered_count} applications."

    return JobCalibrationResponse(
        id=job.id,
        calibration_summary=job.calibration_summary,
        evaluation_framework=job.evaluation_framework,
        calibrated_at=job.calibrated_at,
        message=message,
    )


@router.get("/{job_id}/calibration", response_model=JobCalibrationResponse, tags=["Jobs"])
async def get_job_calibration(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get calibration results for a job.

    - Multi-tenant: Can only get calibration for jobs from user's company
    - Returns calibration_summary, evaluation_framework, and calibrated_at
    """
    service = JobService(db)
    job = await service.get_calibration(current_user["company_id"], job_id)

    return JobCalibrationResponse(
        id=job.id,
        calibration_summary=job.calibration_summary,
        evaluation_framework=job.evaluation_framework,
        calibrated_at=job.calibrated_at,
        message="Calibration retrieved successfully"
        if job.calibrated_at
        else "Job not calibrated yet",
    )


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
    service = JobService(db)
    job = await service.get_public_job(slug)

    # Increment view count in background
    background_tasks.add_task(service.increment_view_count, job.id)

    return job


# ============================================================================
# Job Applications Endpoints
# ============================================================================


@router.get("/{job_id}/applications", response_model=ApplicationListResponse, tags=["Applications"])
async def list_job_applications(
    job_id: UUID,
    status: str | None = Query(None, description="Filter by status (comma-separated)"),
    tier: str | None = Query(None, description="Filter by evaluation tier (comma-separated)"),
    is_dealbreaker: bool | None = Query(None, description="Filter by dealbreaker status"),
    is_flagged: bool | None = Query(None, description="Filter by flagged status"),
    search: str | None = Query(None, max_length=100, description="Search by name or email"),
    sort_by: str | None = Query(
        None, pattern="^(applied_at|name|status|ai_score)$", description="Sort field"
    ),
    sort_dir: str | None = Query(None, pattern="^(asc|desc)$", description="Sort direction"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List applications for a job.

    - **status**: Filter by status, comma-separated (e.g., ?status=applied,screening)
    - **tier**: Filter by evaluation tier, comma-separated
    - **is_dealbreaker**: Filter by dealbreaker status (true/false)
    - **is_flagged**: Filter by flagged status (true/false)
    - **search**: Search by candidate name or email
    - **sort_by**: Sort field - applied_at, name, status, ai_score
    - **sort_dir**: Sort direction - asc or desc (default: desc)
    """
    service = JobService(db)
    result = await service.list_job_applications(
        company_id=current_user["company_id"],
        job_id=job_id,
        status_filter=status,
        tier_filter=tier,
        is_dealbreaker=is_dealbreaker,
        is_flagged=is_flagged,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        limit=limit,
    )

    return ApplicationListResponse(
        data=[ApplicationListItem.model_validate(app) for app in result.applications],
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=result.total,
            total_pages=result.total_pages,
            has_more=result.has_more,
        ),
    )


@router.get(
    "/{job_id}/applications/stats",
    response_model=ApplicationStatsResponse,
    tags=["Applications"],
)
async def get_job_applications_stats(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics summary for applications of a job.

    Returns total count, breakdown by status, and breakdown by evaluation tier.
    """
    service = JobService(db)
    stats = await service.get_job_applications_stats(current_user["company_id"], job_id)

    return ApplicationStatsResponse(
        total_candidates=stats.total_candidates,
        by_status=stats.by_status,
        by_tier=stats.by_tier,
    )
