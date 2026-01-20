"""Job business logic service."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.application import Application
from app.models.job import Job
from app.schemas.job import (
    CalibrationSaveRequest,
    JobCreate,
    JobUpdate,
)

# Constants for validation
VALID_STATUSES = {"applied", "screening", "interviewing", "offer", "hired", "rejected"}
VALID_TIERS = {"strong_match", "good_match", "moderate_match", "weak_match", "mismatch"}


@dataclass
class JobStats:
    """Comprehensive job statistics."""

    # Application counts
    total_applications: int
    today_applications: int
    week_applications: int
    month_applications: int

    # By status
    applied_count: int
    screening_count: int
    interviewing_count: int
    offer_count: int
    hired_count: int
    rejected_count: int

    # View stats
    views_count: int

    # Quality metrics
    application_rate: float
    screening_rate: float
    interview_rate: float
    offer_rate: float
    hire_rate: float

    # Activity metrics
    latest_application_at: datetime | None
    days_since_last_application: int | None
    days_since_published: int | None
    is_recently_active: bool

    # Pipeline
    conversion_rate: float

    # Timestamp
    generated_at: datetime


@dataclass
class ApplicationListResult:
    """Result of application list query."""

    applications: list
    total: int
    total_pages: int
    has_more: bool


@dataclass
class ApplicationStats:
    """Application statistics for a job."""

    total_candidates: int
    by_status: dict[str, int]
    by_tier: dict[str, int]


class JobService:
    """Service for job-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_slug(title: str, job_id: UUID) -> str:
        """
        Generate URL-friendly slug from job title and ID.

        Format: {sanitized-title}-{full-uuid}
        - Title is sanitized (lowercase, alphanumeric + hyphens only)
        - Full UUID ensures uniqueness (no collisions possible)
        """
        sanitized = re.sub(r"[^a-z0-9\s-]", "", title.lower())
        sanitized = re.sub(r"[\s-]+", "-", sanitized).strip("-")
        sanitized = sanitized[:50].rstrip("-")
        return f"{sanitized}-{str(job_id)}"

    async def create_job(
        self, company_id: str | UUID, user_id: str | UUID, data: JobCreate
    ) -> Job:
        """
        Create a new job posting.

        Args:
            company_id: Company ID for multi-tenant isolation
            user_id: User ID of the creator
            data: Job creation data

        Returns:
            Created Job with relations loaded
        """
        job_id = uuid4()
        slug = self.generate_slug(data.title, job_id)

        job = Job(
            id=job_id,
            company_id=company_id,
            created_by=user_id,
            title=data.title,
            description=data.description,
            position_type=data.position_type,
            experience_level=data.experience_level,
            department=data.department,
            location_type=data.location_type,
            location_city=data.location_city,
            location_state=data.location_state,
            location_country=data.location_country,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            salary_currency=data.salary_currency,
            status=data.status,
            slug=slug,
        )

        if data.status == "active":
            job.published_at = datetime.now(timezone.utc)

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        return await self._load_job_relations(job.id)

    async def list_jobs(
        self, company_id: str | UUID, page: int = 1, limit: int = 20
    ) -> tuple[list[dict], int, int]:
        """
        List jobs for a company with pagination.

        Args:
            company_id: Company ID for filtering
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Tuple of (jobs list, total count, total pages)
        """
        # Count total jobs (excluding soft-deleted)
        count_stmt = (
            select(func.count())
            .select_from(Job)
            .where(Job.company_id == company_id, Job.deleted_at.is_(None))
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        pages = (total + limit - 1) // limit
        offset = (page - 1) * limit

        # Get jobs with applications count
        stmt = (
            select(Job, func.count(Application.id).label("applications_count"))
            .outerjoin(
                Application,
                (Application.job_id == Job.id) & (Application.deleted_at.is_(None)),
            )
            .where(Job.company_id == company_id, Job.deleted_at.is_(None))
            .options(selectinload(Job.creator))
            .group_by(Job.id)
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        jobs_with_counts = []

        for row in result:
            job = row[0]
            app_count = row[1]
            jobs_with_counts.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "slug": job.slug,
                    "status": job.status,
                    "position_type": job.position_type,
                    "location_type": job.location_type,
                    "views_count": job.views_count,
                    "applications_count": app_count,
                    "created_by": job.created_by,
                    "creator": job.creator,
                    "published_at": job.published_at,
                    "created_at": job.created_at,
                    "calibrated_at": job.calibrated_at,
                }
            )

        return jobs_with_counts, total, pages

    async def get_job(self, company_id: str | UUID, job_id: UUID) -> Job:
        """
        Get job by ID with multi-tenant filtering.

        Args:
            company_id: Company ID for access control
            job_id: Job ID to retrieve

        Returns:
            Job with relations loaded

        Raises:
            NotFoundError: If job doesn't exist or doesn't belong to company
        """
        stmt = (
            select(Job)
            .where(Job.id == job_id, Job.company_id == company_id)
            .options(selectinload(Job.creator), selectinload(Job.company))
        )

        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        return job

    async def update_job(
        self, company_id: str | UUID, job_id: UUID, data: JobUpdate
    ) -> Job:
        """
        Update job details.

        Args:
            company_id: Company ID for access control
            job_id: Job ID to update
            data: Update data

        Returns:
            Updated Job with relations

        Raises:
            NotFoundError: If job doesn't exist or doesn't belong to company
        """
        stmt = select(Job).where(Job.id == job_id, Job.company_id == company_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        old_status = job.status

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)

        # Set published_at if status changed to active and not already set
        if job.status == "active" and old_status != "active" and job.published_at is None:
            job.published_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(job)

        return await self._load_job_relations(job.id)

    async def get_job_stats(self, company_id: str | UUID, job_id: UUID) -> JobStats:
        """
        Get comprehensive statistics for a job.

        Args:
            company_id: Company ID for access control
            job_id: Job ID

        Returns:
            JobStats with all metrics

        Raises:
            NotFoundError: If job doesn't exist
        """
        # Verify job exists
        result = await self.db.execute(
            select(Job).where(
                Job.id == job_id,
                Job.company_id == company_id,
                Job.deleted_at.is_(None),
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Single efficient query
        query = select(
            func.count(Application.id).label("total_applications"),
            func.count(
                case((Application.created_at >= today_start, Application.id), else_=None)
            ).label("today_applications"),
            func.count(
                case((Application.created_at >= week_ago, Application.id), else_=None)
            ).label("week_applications"),
            func.count(
                case((Application.created_at >= month_ago, Application.id), else_=None)
            ).label("month_applications"),
            func.count(
                case((Application.status == "applied", Application.id), else_=None)
            ).label("applied_count"),
            func.count(
                case((Application.status == "screening", Application.id), else_=None)
            ).label("screening_count"),
            func.count(
                case((Application.status == "interviewing", Application.id), else_=None)
            ).label("interviewing_count"),
            func.count(
                case((Application.status == "offer", Application.id), else_=None)
            ).label("offer_count"),
            func.count(
                case((Application.status == "hired", Application.id), else_=None)
            ).label("hired_count"),
            func.count(
                case((Application.status == "rejected", Application.id), else_=None)
            ).label("rejected_count"),
            func.max(Application.created_at).label("latest_application_at"),
        ).where(
            Application.job_id == job_id,
            Application.deleted_at.is_(None),
        )

        result = await self.db.execute(query)
        row = result.one()

        # Extract counts
        total_apps = row.total_applications or 0
        applied_count = row.applied_count or 0
        screening_count = row.screening_count or 0
        interviewing_count = row.interviewing_count or 0
        offer_count = row.offer_count or 0
        hired_count = row.hired_count or 0
        rejected_count = row.rejected_count or 0

        # Calculate quality metrics
        views_count = job.views_count or 0
        application_rate = (total_apps / views_count * 100) if views_count > 0 else 0.0

        screening_plus = screening_count + interviewing_count + offer_count + hired_count
        screening_rate = (screening_plus / total_apps * 100) if total_apps > 0 else 0.0

        interview_plus = interviewing_count + offer_count + hired_count
        interview_rate = (interview_plus / total_apps * 100) if total_apps > 0 else 0.0

        offer_plus = offer_count + hired_count
        offer_rate = (offer_plus / total_apps * 100) if total_apps > 0 else 0.0

        hire_rate = (hired_count / total_apps * 100) if total_apps > 0 else 0.0

        # Activity metrics
        latest_application_at = row.latest_application_at
        days_since_last_application = None
        is_recently_active = False

        if latest_application_at:
            days_since_last_application = (now - latest_application_at).days
            is_recently_active = days_since_last_application <= 7

        days_since_published = None
        if job.published_at:
            days_since_published = (now - job.published_at).days

        return JobStats(
            total_applications=total_apps,
            today_applications=row.today_applications or 0,
            week_applications=row.week_applications or 0,
            month_applications=row.month_applications or 0,
            applied_count=applied_count,
            screening_count=screening_count,
            interviewing_count=interviewing_count,
            offer_count=offer_count,
            hired_count=hired_count,
            rejected_count=rejected_count,
            views_count=views_count,
            application_rate=round(application_rate, 2),
            screening_rate=round(screening_rate, 2),
            interview_rate=round(interview_rate, 2),
            offer_rate=round(offer_rate, 2),
            hire_rate=round(hire_rate, 2),
            latest_application_at=latest_application_at,
            days_since_last_application=days_since_last_application,
            days_since_published=days_since_published,
            is_recently_active=is_recently_active,
            conversion_rate=round(hire_rate, 2),
            generated_at=now,
        )

    async def save_calibration(
        self,
        company_id: str | UUID,
        job_id: UUID,
        data: CalibrationSaveRequest,
    ) -> Job:
        """
        Save calibration results for a job.

        Args:
            company_id: Company ID for access control
            job_id: Job ID
            data: Calibration data

        Returns:
            Updated Job

        Raises:
            NotFoundError: If job doesn't exist
        """
        stmt = select(Job).where(Job.id == job_id, Job.company_id == company_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        job.calibration_summary = data.calibration_summary
        job.evaluation_framework = data.evaluation_framework
        job.calibrated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(job)

        return job

    async def get_calibration(self, company_id: str | UUID, job_id: UUID) -> Job:
        """
        Get calibration results for a job.

        Args:
            company_id: Company ID for access control
            job_id: Job ID

        Returns:
            Job with calibration data

        Raises:
            NotFoundError: If job doesn't exist
        """
        stmt = select(Job).where(Job.id == job_id, Job.company_id == company_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(message="Job not found", code="job_not_found")

        return job

    async def get_public_job(self, slug: str) -> Job:
        """
        Get public job by slug (for candidates).

        Args:
            slug: Job slug

        Returns:
            Job with company relation

        Raises:
            NotFoundError: If job doesn't exist or is a draft
        """
        stmt = select(Job).where(Job.slug == slug).options(selectinload(Job.company))
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job or job.status == "draft":
            raise NotFoundError(message="Job not found", code="job_not_found")

        return job

    async def increment_view_count(self, job_id: UUID) -> None:
        """Increment job view count (for background task)."""
        stmt = select(Job).where(Job.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if job:
            job.views_count += 1
            await self.db.commit()

    async def list_job_applications(
        self,
        company_id: str | UUID,
        job_id: UUID,
        status_filter: str | None = None,
        tier_filter: str | None = None,
        is_dealbreaker: bool | None = None,
        is_flagged: bool | None = None,
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ApplicationListResult:
        """
        List applications for a job with filtering and pagination.

        Args:
            company_id: Company ID for access control
            job_id: Job ID
            status_filter: Comma-separated status values
            tier_filter: Comma-separated tier values
            is_dealbreaker: Filter by dealbreaker status
            is_flagged: Filter by flagged status
            search: Search term for name/email
            sort_by: Sort field (applied_at, name, status, ai_score)
            sort_dir: Sort direction (asc, desc)
            page: Page number
            limit: Items per page

        Returns:
            ApplicationListResult with applications and pagination info

        Raises:
            NotFoundError: If job doesn't exist
            ValidationError: If filter values are invalid
        """
        # Parse and validate filters
        status_list = self._parse_filter_values(status_filter, VALID_STATUSES, "status")
        tier_list = self._parse_filter_values(tier_filter, VALID_TIERS, "tier")

        # Verify job exists
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.company_id == company_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(message="Job not found", code="job_not_found")

        # Build query
        query = select(Application).where(
            Application.job_id == job_id, Application.deleted_at.is_(None)
        )

        if status_list:
            query = query.where(Application.status.in_(status_list))
        if tier_list:
            query = query.where(Application.evaluation_tier.in_(tier_list))
        if is_dealbreaker is not None:
            query = query.where(Application.is_dealbreaker == is_dealbreaker)
        if is_flagged is not None:
            query = query.where(Application.is_flagged == is_flagged)

        # Apply search
        if search:
            search_term = f"%{search.lower()}%"
            query = query.where(
                (func.lower(Application.first_name).like(search_term))
                | (func.lower(Application.last_name).like(search_term))
                | (func.lower(Application.email).like(search_term))
                | (
                    func.lower(
                        func.concat(Application.first_name, " ", Application.last_name)
                    ).like(search_term)
                )
            )

        # Apply sorting
        sort_column = self._get_sort_column(sort_by)
        if (sort_dir or "desc") == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Get total count
        total = await self._get_filtered_count(
            job_id, status_list, tier_list, is_dealbreaker, is_flagged, search
        )

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        applications = list(result.scalars().all())

        total_pages = (total + limit - 1) // limit
        has_more = page < total_pages

        return ApplicationListResult(
            applications=applications,
            total=total,
            total_pages=total_pages,
            has_more=has_more,
        )

    async def get_job_applications_stats(
        self, company_id: str | UUID, job_id: UUID
    ) -> ApplicationStats:
        """
        Get application statistics for a job.

        Args:
            company_id: Company ID for access control
            job_id: Job ID

        Returns:
            ApplicationStats with counts by status and tier

        Raises:
            NotFoundError: If job doesn't exist
        """
        # Verify job exists
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.company_id == company_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(message="Job not found", code="job_not_found")

        # Aggregate query
        result = await self.db.execute(
            select(
                Application.status,
                Application.evaluation_tier,
                func.count().label("count"),
            )
            .where(Application.job_id == job_id, Application.deleted_at.is_(None))
            .group_by(Application.status, Application.evaluation_tier)
        )
        rows = result.all()

        total_candidates = 0
        by_status: dict[str, int] = {}
        by_tier: dict[str, int] = {}

        for row in rows:
            total_candidates += row.count
            by_status[row.status] = by_status.get(row.status, 0) + row.count
            if row.evaluation_tier:
                by_tier[row.evaluation_tier] = (
                    by_tier.get(row.evaluation_tier, 0) + row.count
                )

        return ApplicationStats(
            total_candidates=total_candidates,
            by_status=by_status,
            by_tier=by_tier,
        )

    # Private helper methods

    async def _load_job_relations(self, job_id: UUID) -> Job:
        """Load job with creator and company relations."""
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .options(selectinload(Job.creator), selectinload(Job.company))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    def _parse_filter_values(
        self, filter_str: str | None, valid_values: set, field_name: str
    ) -> list[str] | None:
        """Parse comma-separated filter values and validate."""
        if not filter_str:
            return None

        values = [v.strip() for v in filter_str.split(",") if v.strip()]
        invalid = set(values) - valid_values
        if invalid:
            raise ValidationError(
                message=f"Invalid {field_name} values: {', '.join(invalid)}",
                code=f"invalid_{field_name}",
            )
        return values

    def _get_sort_column(self, sort_by: str | None):
        """Get SQLAlchemy column for sorting."""
        sort_columns = {
            "name": Application.first_name,
            "status": Application.status,
            "ai_score": Application.evaluation_score,
        }
        return sort_columns.get(sort_by, Application.applied_at)

    async def _get_filtered_count(
        self,
        job_id: UUID,
        status_list: list[str] | None,
        tier_list: list[str] | None,
        is_dealbreaker: bool | None,
        is_flagged: bool | None,
        search: str | None,
    ) -> int:
        """Get count of applications matching filters."""
        count_query = (
            select(func.count())
            .select_from(Application)
            .where(Application.job_id == job_id, Application.deleted_at.is_(None))
        )

        if status_list:
            count_query = count_query.where(Application.status.in_(status_list))
        if tier_list:
            count_query = count_query.where(Application.evaluation_tier.in_(tier_list))
        if is_dealbreaker is not None:
            count_query = count_query.where(Application.is_dealbreaker == is_dealbreaker)
        if is_flagged is not None:
            count_query = count_query.where(Application.is_flagged == is_flagged)
        if search:
            search_term = f"%{search.lower()}%"
            count_query = count_query.where(
                (func.lower(Application.first_name).like(search_term))
                | (func.lower(Application.last_name).like(search_term))
                | (func.lower(Application.email).like(search_term))
                | (
                    func.lower(
                        func.concat(Application.first_name, " ", Application.last_name)
                    ).like(search_term)
                )
            )

        result = await self.db.execute(count_query)
        return result.scalar() or 0
