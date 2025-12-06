"""Job onboarding endpoints - AI-powered calibration questions generation."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import get_current_user
from app.llm.baml.baml_client import b
from app.llm.baml.baml_client.types import JobInput

logger = logging.getLogger(__name__)

router = APIRouter()


class ExperienceRange(BaseModel):
    """Experience range in years."""

    model_config = ConfigDict(populate_by_name=True)

    min_years: int | None = Field(None, alias="min")
    max_years: int | None = Field(None, alias="max")


class JobOnboardingRequest(BaseModel):
    """Request schema for generating job onboarding questions."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str
    position_type: str = Field(..., alias="positionType")
    department: str | None = None
    location_type: str = Field(..., alias="locationType")
    experience_range: ExperienceRange | None = Field(None, alias="experienceRange")


@router.post("/questions", tags=["Onboarding"])
async def generate_onboarding_questions(
    request: JobOnboardingRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate AI-powered calibration questions for job onboarding.

    Takes basic job information and generates tailored calibration questions
    including skill assessments, trade-off scenarios, and role expectations.
    """
    try:
        job_input = JobInput(
            title=request.title,
            description=request.description,
            positionType=request.position_type,
            department=request.department,
            locationType=request.location_type,
            experienceMin=request.experience_range.min_years if request.experience_range else None,
            experienceMax=request.experience_range.max_years if request.experience_range else None,
        )

        logger.info(
            "Generating onboarding questions",
            extra={"job_title": request.title, "user_id": current_user["user_id"]},
        )

        baml_response = b.GenerateJobOnboardingQuestions(job=job_input)

        return {"jobId": str(uuid.uuid4()), **baml_response.model_dump()}

    except Exception as e:
        logger.exception("Failed to generate onboarding questions")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate onboarding questions: {str(e)}"
        ) from e
