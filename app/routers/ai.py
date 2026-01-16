"""AI endpoints for job parsing, framework creation, and candidate evaluation."""

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.schemas.ai import (
    CreateFrameworkResponse,
    EvaluateCandidateRequest,
    EvaluateCandidateResponse,
    ParseJobRequest,
    ParseJobResponse,
    ParseResumeRequest,
    ParseResumeResponse,
    PostProcessingMetadata,
    ScoresResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Job Parsing
# ============================================================================


@router.post("/jobs/parse", response_model=ParseJobResponse, tags=["AI"])
def parse_job_description(
    request: ParseJobRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Parse a job description and generate calibration questions.

    Takes basic job information, parses it using AI to extract skills,
    responsibilities, and role complexity, then generates calibration
    questions tailored to this specific role.
    """
    start = time.time()
    try:
        from subtribe_ai import parse_job_description

        # Create job data dict for subtribe-ai
        job_data = {
            "title": request.title,
            "description": request.description,
            "positionType": request.positionType,
            "department": request.department,
            "locationType": request.locationType,
            "experienceMin": request.experienceRange.min if request.experienceRange else None,
            "experienceMax": request.experienceRange.max if request.experienceRange else None,
        }

        # Call subtribe-ai function
        result = parse_job_description(job_data)

        # Add jobId for frontend
        response = ParseJobResponse(
            jobId=str(uuid.uuid4()),
            roleAnalysis=result.get("roleAnalysis", {}),
            calibrationQuestions=result.get("calibrationQuestions", {}),
        )

        elapsed = time.time() - start
        logger.info(f"[parse] {request.title} - {elapsed:.2f}s")
        return response

    except Exception as e:
        logger.exception(f"Failed to parse job description: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse job description: {str(e)}",
        ) from e


# ============================================================================
# Framework Creation
# ============================================================================


@router.post("/jobs/create-framework", response_model=CreateFrameworkResponse, tags=["AI"])
def create_evaluation_framework(
    request: dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """
    Create an evaluation framework from calibration decisions.

    Takes the calibration summary JSON (with LLM suggestions and user selections)
    and generates a structured evaluation framework for assessing candidates.

    Post-processing pipeline is applied to:
    1. Validate completeness (error if >30% missing, add defaults if <=30%)
    2. Fix ID mismatches using Levenshtein distance
    3. Normalize weights to sum to 1.0
    4. Apply selection multipliers (1.0 selected, 0.3 unselected)
    5. Validate custom item boost
    6. Validate skill counts
    7. Compare dimension weights with derived (warn if >20% divergence)
    8. Review suspicious items
    """
    start = time.time()
    try:
        from subtribe_ai import create_framework

        # Call subtribe-ai function
        result = create_framework(request)

        # Build response
        response = CreateFrameworkResponse(
            framework=result.get("framework", {}),
            post_processing=PostProcessingMetadata(
                errors=result.get("post_processing", {}).get("errors", []),
                warnings=result.get("post_processing", {}).get("warnings", []),
                requires_human_review=result.get("post_processing", {}).get(
                    "requires_human_review", False
                ),
                metadata=result.get("post_processing", {}).get("metadata", {}),
            ),
        )

        elapsed = time.time() - start
        title = request.get("basicJobInfo", {}).get("title", "Unknown")
        logger.info(f"[framework] {title} - {elapsed:.2f}s")
        return response

    except Exception as e:
        logger.exception(f"Failed to create evaluation framework: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create evaluation framework: {str(e)}",
        ) from e


# ============================================================================
# Resume Parsing
# ============================================================================


@router.post("/resume/parse", response_model=ParseResumeResponse, tags=["AI"])
def parse_resume(
    request: ParseResumeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Parse a markdown resume into structured JSON.

    Converts unstructured resume text into structured data with:
    - Personal info (name, email, phone, links)
    - Experience entries with calculated durations
    - Education with degree levels
    - Projects with categories
    - Skills (technical, soft, languages)
    - Certifications, publications, awards
    - Other sections (activities, volunteer, etc.)

    Post-processing calculates:
    - Duration from dates (LLM never does math)
    - Employment gaps and overlaps
    - Years since graduation
    - Date anomalies (inverted, future dates, etc.)

    Link preprocessing:
    - Derives GitHub profile from repo URLs
    - Groups links by type for better matching
    """
    start = time.time()
    try:
        from subtribe_ai import parse_resume_markdown

        # Convert link mappings to dict format
        link_mappings = None
        if request.link_mappings:
            link_mappings = [
                {"display_text": lm.display_text, "url": lm.url} for lm in request.link_mappings
            ]

        # Call subtribe-ai function
        # Returns: {"markdown": str, "parsed": dict}
        result = parse_resume_markdown(
            markdown_text=request.resume_markdown,
            link_mappings=link_mappings,
        )

        elapsed = time.time() - start
        parsed = result["parsed"]

        # Build response
        response = ParseResumeResponse(
            personal_info=parsed.get("personal_info", {}),
            experience=parsed.get("experience", {}),
            education=parsed.get("education", {}),
            skills=parsed.get("skills", {}),
            projects=parsed.get("projects"),
            certifications=parsed.get("certifications"),
            markdown=result["markdown"],
            timing={"seconds": round(elapsed, 2)},
        )

        name = parsed.get("personal_info", {}).get("full_name", "Unknown")
        total_months = parsed.get("experience", {}).get("summary", {}).get("total_months", 0)
        logger.info(f"[resume] {name} - {total_months}mo exp - {elapsed:.2f}s")
        return response

    except Exception as e:
        logger.exception(f"Failed to parse resume: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}",
        ) from e


# ============================================================================
# Candidate Evaluation
# ============================================================================


@router.post("/candidates/evaluate", response_model=EvaluateCandidateResponse, tags=["AI"])
def evaluate_candidate(
    request: EvaluateCandidateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Evaluate a parsed candidate resume against an evaluation framework.

    Expects:
    - parsed_resume: Output from parse_resume_markdown() or parse_resume()
    - framework: Evaluation framework from create_framework()

    Returns scored evaluation with:
    - Final score (0-10)
    - Tier (strong_match, good_match, moderate_match, weak_match, mismatch)
    - Dimension scores (technical_fit, experience_fit, etc.)
    - Skill matches with evidence
    - Constraint results
    - Tradeoff analysis
    - Summary with strengths, concerns, and interview questions
    - Blockers and warnings
    """
    start = time.time()
    try:
        from subtribe_ai import evaluate_candidate as ai_evaluate_candidate

        # Call subtribe-ai function with parsed resume dict
        result = ai_evaluate_candidate(
            request.parsed_resume,
            request.framework,
        )

        elapsed = time.time() - start

        # Build response - structure matches subtribe-ai output
        scores = result.get("scores", {})
        response = EvaluateCandidateResponse(
            scores=ScoresResult(
                final_score=scores.get("final_score", 0.0),
                tier=scores.get("tier", "mismatch"),
                dimension_scores=scores.get("dimension_scores", {}),
                verification_confidence=scores.get("verification_confidence", "medium"),
            ),
            manipulation_check=result.get("manipulation_check", {}),
            red_flags=result.get("red_flags", {}),
            blockers=result.get("blockers", []),
            can_proceed=result.get("can_proceed", True),
            analysis=result.get("analysis", {}),
            evaluation=result.get("evaluation", {}),
            warnings=result.get("warnings"),
            timing=result.get("timing"),
        )

        final_score = scores.get("final_score", 0)
        tier = scores.get("tier", "unknown")
        logger.info(f"[evaluate] Score: {final_score} ({tier}) - {elapsed:.2f}s")
        return response

    except Exception as e:
        logger.exception(f"Failed to evaluate candidate: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate candidate: {str(e)}",
        ) from e
