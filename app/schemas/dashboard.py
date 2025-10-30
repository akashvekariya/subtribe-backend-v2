"""Dashboard statistics schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobStats(BaseModel):
    """Job statistics."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    active: int
    draft: int
    closed: int


class ApplicationsByStatus(BaseModel):
    """Applications grouped by status."""

    model_config = ConfigDict(from_attributes=True)

    applied: int
    screening: int
    interviewing: int
    offer: int
    hired: int
    rejected: int


class ApplicationStats(BaseModel):
    """Application statistics."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    today: int
    this_week: int
    this_month: int
    by_status: ApplicationsByStatus


class PipelineStats(BaseModel):
    """Pipeline conversion metrics (optional)."""

    model_config = ConfigDict(from_attributes=True)

    conversion_rate: float
    avg_time_to_hire_days: float | None = None


class ActivityStats(BaseModel):
    """Activity metrics (optional)."""

    model_config = ConfigDict(from_attributes=True)

    views_today: int
    views_this_week: int


class DashboardStatsResponse(BaseModel):
    """Dashboard statistics response."""

    model_config = ConfigDict(from_attributes=True)

    jobs: JobStats
    applications: ApplicationStats
    pipeline: PipelineStats | None = None
    activity: ActivityStats | None = None
    generated_at: datetime
