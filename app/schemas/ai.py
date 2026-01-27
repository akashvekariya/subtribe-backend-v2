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
    """Response from resume parsing.

    Structure:
    - personal_info: Personal details (name, email, phone, links, location)
    - experience: {summary: {...}, entries: [...]} with duration_months in each entry
    - education: {summary: {...}, entries: [...]} with highest_level and months_since_graduation
    - projects: {summary: {...}, entries: [...]} with duration_months in each entry
    - skills, certifications: As before
    - markdown: The extracted markdown text
    """

    personal_info: dict[str, Any]
    experience: dict[str, Any]  # {summary: {...}, entries: [...]}
    education: dict[str, Any]  # {summary: {...}, entries: [...]}
    skills: dict[str, Any]
    projects: dict[str, Any] | None = None  # {summary: {...}, entries: [...]}
    certifications: list[dict[str, Any]] | None = None
    markdown: str | None = None
    timing: dict[str, Any] | None = None


# ============================================================================
# Candidate Evaluation
# ============================================================================


class EvaluateCandidateRequest(BaseModel):
    """Request to evaluate a candidate against a framework."""

    framework: dict[str, Any]
    parsed_resume: dict[str, Any]  # Parsed resume JSON from parse_resume_markdown()


class ScoresResult(BaseModel):
    """Scores from candidate evaluation."""

    final_score: float
    tier: str
    dimension_scores: dict[str, float]
    verification_confidence: str = "medium"


class EvaluateCandidateResponse(BaseModel):
    """Response from candidate evaluation.

    Structure matches subtribe-ai EvaluationResult:
    - scores: final_score, tier, dimension_scores, verification_confidence
    - manipulation_check: detected, details
    - red_flags: flags list and summary
    - blockers: list of blocking issues (dealbreaker failures)
    - can_proceed: whether candidate passes initial screening
    - analysis: skill_analysis, constraint_analysis, tradeoff_analysis, source_summary
    - evaluation: experience_entries, skill_matches, constraint_results, etc.
    - warnings: list of post-processing warnings
    - timing: evaluation timing info
    """

    scores: ScoresResult
    manipulation_check: dict[str, Any]
    red_flags: dict[str, Any]
    blockers: list[dict[str, Any]]
    can_proceed: bool
    analysis: dict[str, Any]
    evaluation: dict[str, Any]
    warnings: list[dict[str, Any]] | None = None
    timing: dict[str, Any] | None = None
