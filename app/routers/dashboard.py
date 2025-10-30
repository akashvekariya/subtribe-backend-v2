"""Dashboard statistics endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.application import Application
from app.models.job import Job
from app.schemas.dashboard import (
    ApplicationsByStatus,
    ApplicationStats,
    DashboardStatsResponse,
    JobStats,
    PipelineStats,
)

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsResponse, tags=["Dashboard"])
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics for the authenticated company.

    Returns comprehensive stats including:
    - Job counts by status
    - Application counts by status and time period
    - Pipeline conversion metrics

    Args:
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        DashboardStatsResponse with all statistics
    """
    company_id: UUID = current_user["company_id"]

    # Get current timestamp for date calculations
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Efficient single query with conditional counts
    # Using LEFT JOIN to include jobs without applications
    query = (
        select(
            # Job statistics
            func.count(func.distinct(Job.id)).label("total_jobs"),
            func.count(func.distinct(case((Job.status == "active", Job.id), else_=None))).label(
                "active_jobs"
            ),
            func.count(func.distinct(case((Job.status == "draft", Job.id), else_=None))).label(
                "draft_jobs"
            ),
            func.count(func.distinct(case((Job.status == "closed", Job.id), else_=None))).label(
                "closed_jobs"
            ),
            # Application statistics - total
            func.count(func.distinct(Application.id)).label("total_applications"),
            # Applications by time period
            func.count(
                func.distinct(
                    case(
                        (Application.created_at >= today_start, Application.id),
                        else_=None,
                    )
                )
            ).label("today_applications"),
            func.count(
                func.distinct(
                    case(
                        (Application.created_at >= week_ago, Application.id),
                        else_=None,
                    )
                )
            ).label("week_applications"),
            func.count(
                func.distinct(
                    case(
                        (Application.created_at >= month_ago, Application.id),
                        else_=None,
                    )
                )
            ).label("month_applications"),
            # Applications by status
            func.count(
                func.distinct(case((Application.status == "applied", Application.id), else_=None))
            ).label("applied_count"),
            func.count(
                func.distinct(case((Application.status == "screening", Application.id), else_=None))
            ).label("screening_count"),
            func.count(
                func.distinct(
                    case((Application.status == "interviewing", Application.id), else_=None)
                )
            ).label("interviewing_count"),
            func.count(
                func.distinct(case((Application.status == "offer", Application.id), else_=None))
            ).label("offer_count"),
            func.count(
                func.distinct(case((Application.status == "hired", Application.id), else_=None))
            ).label("hired_count"),
            func.count(
                func.distinct(case((Application.status == "rejected", Application.id), else_=None))
            ).label("rejected_count"),
        )
        .select_from(Job)
        .outerjoin(
            Application,
            and_(
                Application.job_id == Job.id,
                Application.deleted_at.is_(None),  # Exclude soft-deleted applications
            ),
        )
        .where(
            Job.company_id == company_id,
            Job.deleted_at.is_(None),  # Exclude soft-deleted jobs
        )
    )

    result = await db.execute(query)
    row = result.one()

    # Calculate pipeline metrics
    hired_count = row.hired_count or 0
    total_apps = row.total_applications or 0
    conversion_rate = (hired_count / total_apps * 100) if total_apps > 0 else 0.0

    # Build response
    return DashboardStatsResponse(
        jobs=JobStats(
            total=row.total_jobs or 0,
            active=row.active_jobs or 0,
            draft=row.draft_jobs or 0,
            closed=row.closed_jobs or 0,
        ),
        applications=ApplicationStats(
            total=total_apps,
            today=row.today_applications or 0,
            this_week=row.week_applications or 0,
            this_month=row.month_applications or 0,
            by_status=ApplicationsByStatus(
                applied=row.applied_count or 0,
                screening=row.screening_count or 0,
                interviewing=row.interviewing_count or 0,
                offer=row.offer_count or 0,
                hired=hired_count,
                rejected=row.rejected_count or 0,
            ),
        ),
        pipeline=PipelineStats(
            conversion_rate=round(conversion_rate, 2),
            avg_time_to_hire_days=None,  # TODO: Implement in future iteration
        ),
        activity=None,  # TODO: Implement view tracking in future iteration
        generated_at=now,
    )
