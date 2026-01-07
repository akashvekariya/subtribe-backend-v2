"""Pydantic schemas for AI endpoints."""

from typing import Any

from pydantic import BaseModel

# ============================================================================
# Job Parsing
# ============================================================================


class JobLocation(BaseModel):
    """Location details for a job."""

    city: str | None = None
    state: str | None = None
    country: str | None = None


class JobSalary(BaseModel):
    """Salary information for a job."""

    currency: str = "INR"
    min: int | None = None
    max: int | None = None
    showOnPost: bool = False


class ExperienceRange(BaseModel):
    """Experience range requirements."""

    min: int | None = None
    max: int | None = None


class ScreeningQuestion(BaseModel):
    """Screening question for job application."""

    id: str
    text: str
    type: str
    required: bool
    options: list[str] | None = None


class ParseJobRequest(BaseModel):
    """Request to parse a job description."""

    title: str
    description: str
    positionType: str
    department: str | None = None
    locationType: str
    location: JobLocation | None = None
    salary: JobSalary | None = None
    experienceRange: ExperienceRange | None = None
    screeningQuestions: list[ScreeningQuestion] | None = None


class ParseJobResponse(BaseModel):
    """Response from job parsing."""

    jobId: str
    roleAnalysis: dict[str, Any]
    calibrationQuestions: dict[str, Any]


# ============================================================================
# Framework Creation
# ============================================================================


class CreateFrameworkRequest(BaseModel):
    """Request to create evaluation framework from calibration decisions."""

    # This is a dict because the calibration response structure is complex
    # and varies based on user selections
    pass


class PostProcessingMetadata(BaseModel):
    """Post-processing metadata from framework creation."""

    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    requires_human_review: bool
    metadata: dict[str, Any]


class CreateFrameworkResponse(BaseModel):
    """Response from framework creation."""

    framework: dict[str, Any]
    post_processing: PostProcessingMetadata


# ============================================================================
# Fact Extraction
# ============================================================================


class ExtractFactsRequest(BaseModel):
    """Request to extract facts from a resume."""

    resume_text: str
    skill_ids: list[str] | None = None


class ExtractFactsResponse(BaseModel):
    """Response from fact extraction."""

    experience: dict[str, Any]
    education: list[dict[str, Any]]
    certifications: list[dict[str, Any]]
    skill_keywords: list[str]
    timing: dict[str, Any] | None = None


# ============================================================================
# Resume Parsing
# ============================================================================


class LinkMapping(BaseModel):
    """Mapping of display text to URL for links."""

    display_text: str
    url: str


class ParseResumeRequest(BaseModel):
    """Request to parse a markdown resume."""

    resume_markdown: str
    link_mappings: list[LinkMapping] | None = None


class ParseResumeResponse(BaseModel):
    """Response from resume parsing."""

    personal_info: dict[str, Any]
    experience: list[dict[str, Any]]
    education: list[dict[str, Any]]
    skills: dict[str, Any]
    projects: list[dict[str, Any]] | None = None
    certifications: list[dict[str, Any]] | None = None
    computed: dict[str, Any]
    timing: dict[str, Any] | None = None


# ============================================================================
# Candidate Evaluation
# ============================================================================


class EvaluateCandidateRequest(BaseModel):
    """Request to evaluate a candidate against a framework."""

    framework: dict[str, Any]
    candidate_resume: str


class ScoresResult(BaseModel):
    """Scores from candidate evaluation."""

    final_score: float
    tier: str
    dimension_scores: dict[str, float]


class EvaluateCandidateResponse(BaseModel):
    """Response from candidate evaluation."""

    scores: ScoresResult
    skill_matches: list[dict[str, Any]]
    constraint_results: dict[str, Any]
    tradeoff_alignment: dict[str, Any]
    summary: dict[str, Any]
    computed_facts: dict[str, Any]
    timing: dict[str, Any] | None = None
