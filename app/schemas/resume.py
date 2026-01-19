"""Resume display schemas.

Schemas for the resume display endpoint that transforms parsed resume JSON
into a clean, structured format for frontend rendering.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# Personal Info
# ============================================================================


class OtherLink(BaseModel):
    """External link from resume."""

    url: str
    label: str | None = None


class PersonalInfo(BaseModel):
    """Candidate's personal/contact information."""

    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    other_links: list[OtherLink] = Field(default_factory=list)


# ============================================================================
# Skills
# ============================================================================


class Skills(BaseModel):
    """Candidate's skills organized by category."""

    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


# ============================================================================
# Experience
# ============================================================================


class ExperienceEntry(BaseModel):
    """Single experience/work history entry."""

    title: str
    company: str
    location: str | None = None
    category: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_ongoing: bool = False
    duration_months: int | None = None
    content: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ExperienceSummary(BaseModel):
    """Aggregated experience metrics."""

    total_months: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    has_overlaps: bool = False
    has_significant_gaps: bool = False


class Experience(BaseModel):
    """Experience section with summary and entries."""

    summary: ExperienceSummary = Field(default_factory=ExperienceSummary)
    entries: list[ExperienceEntry] = Field(default_factory=list)


# ============================================================================
# Education
# ============================================================================


class EducationEntry(BaseModel):
    """Single education entry."""

    degree: str
    institution: str
    field_of_study: str | None = None
    level: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    score_value: str | None = None
    relevant_coursework: list[str] = Field(default_factory=list)


class EducationSummary(BaseModel):
    """Aggregated education metrics."""

    highest_level: str | None = None
    months_since_graduation: int | None = None


class Education(BaseModel):
    """Education section with summary and entries."""

    summary: EducationSummary = Field(default_factory=EducationSummary)
    entries: list[EducationEntry] = Field(default_factory=list)


# ============================================================================
# Projects
# ============================================================================


class ProjectEntry(BaseModel):
    """Single project entry."""

    name: str
    category: str | None = None
    content: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    source_url: str | None = None
    live_url: str | None = None


class Projects(BaseModel):
    """Projects section with entries."""

    entries: list[ProjectEntry] = Field(default_factory=list)


# ============================================================================
# Certifications
# ============================================================================


class Certification(BaseModel):
    """Single certification entry."""

    name: str
    issuer: str | None = None
    date: str | None = None


# ============================================================================
# Main Resume Data
# ============================================================================


class ResumeData(BaseModel):
    """Complete parsed resume data for display."""

    personal_info: PersonalInfo
    professional_summary: str | list[str] | None = None
    skills: Skills = Field(default_factory=Skills)
    experience: Experience = Field(default_factory=Experience)
    education: Education = Field(default_factory=Education)
    projects: Projects = Field(default_factory=Projects)
    certifications: list[Certification] = Field(default_factory=list)


# ============================================================================
# Response Schemas
# ============================================================================


class ResumeDisplayMeta(BaseModel):
    """Metadata about the resume and application context."""

    application_id: UUID
    candidate_name: str
    job_id: UUID
    job_title: str
    resume_filename: str | None = None
    resume_url: str | None = None
    resume_url_expires_at: datetime | None = None
    has_cover_letter: bool = False
    cover_letter: str | None = None
    applied_at: datetime | None = None


class ResumeDisplayResponse(BaseModel):
    """Response for resume display endpoint.

    - data: Transformed resume data for frontend rendering
    - meta: Application context and metadata
    """

    data: ResumeData | None = Field(
        None,
        description="Parsed resume data, null if not yet processed",
    )
    meta: ResumeDisplayMeta
