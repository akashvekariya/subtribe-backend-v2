"""Email endpoints - Send emails and manage templates."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.email.email_service import EmailService
from app.email.template_renderer import TemplateRenderer
from app.models.application import Application
from app.models.email_template import EmailTemplate
from app.models.scheduled_email import ScheduledEmail
from app.schemas.common import BaseResponse

logger = logging.getLogger(__name__)

# Internal router (for Cloud Tasks)
internal_router = APIRouter(tags=["Internal - Emails"])

# Email router (for sending emails)
email_router = APIRouter(tags=["Emails"])

# Admin router (for template management)
router = APIRouter(tags=["Email Templates"])


# ========== Schemas ==========


class SendScheduledEmailRequest(BaseModel):
    """Request to send a scheduled email."""

    scheduled_email_id: UUID = Field(..., description="ID of scheduled email to send")


class SendScheduledEmailResponse(BaseResponse):
    """Response for send scheduled email."""

    success: bool = Field(..., description="Whether email was sent successfully")
    message_id: Optional[str] = Field(None, description="Provider message ID if sent")


class SendEmailRequest(BaseModel):
    """Request to send an email to an application."""

    template_id: Optional[UUID] = Field(None, description="Template ID to use (optional)")
    subject: str = Field(..., min_length=1, max_length=1000, description="Email subject")
    body: str = Field(..., min_length=1, max_length=50000, description="Email body")
    send_immediately: bool = Field(True, description="Send now or schedule for later")
    scheduled_for: Optional[datetime] = Field(None, description="When to send (if not immediately)")


class SendEmailResponse(BaseResponse):
    """Response for sending email."""

    email_id: Optional[UUID] = Field(None, description="ID of scheduled/sent email")
    message_id: Optional[str] = Field(None, description="Provider message ID if sent immediately")
    scheduled_for: Optional[datetime] = Field(None, description="When email will be sent")


class BulkEmailRequest(BaseModel):
    """Request to send bulk emails."""

    application_ids: list[UUID] = Field(..., min_length=1, description="List of application IDs")
    template_id: Optional[UUID] = Field(None, description="Template ID to use (optional)")
    subject: str = Field(..., min_length=1, max_length=1000, description="Email subject template")
    body: str = Field(..., min_length=1, max_length=50000, description="Email body template")
    send_immediately: bool = Field(True, description="Send now or schedule for later")
    scheduled_for: Optional[datetime] = Field(None, description="When to send (if not immediately)")


class BulkEmailResponse(BaseResponse):
    """Response for bulk email send."""

    total: int = Field(..., description="Total emails to send")
    successful: int = Field(..., description="Successfully sent/scheduled")
    failed: int = Field(..., description="Failed to send/schedule")
    email_ids: list[UUID] = Field(default_factory=list, description="IDs of created emails")


class PreviewEmailRequest(BaseModel):
    """Request to preview an email."""

    template_id: Optional[UUID] = Field(None, description="Template ID to use")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")


class PreviewEmailResponse(BaseResponse):
    """Response with preview of rendered email."""

    to_email: str
    to_name: str
    subject: str
    body: str


class EmailTemplateResponse(BaseModel):
    """Email template response."""

    id: UUID
    name: str
    template_type: str
    category: str
    subject: str
    body: str
    wildcards: list[str]
    is_default: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CreateEmailTemplateRequest(BaseModel):
    """Request to create email template."""

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    category: str = Field("custom", description="Template category")
    subject: str = Field(..., min_length=1, max_length=1000, description="Email subject")
    body: str = Field(..., min_length=1, max_length=50000, description="Email body")


class UpdateEmailTemplateRequest(BaseModel):
    """Request to update email template."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None)
    subject: Optional[str] = Field(None, min_length=1, max_length=1000)
    body: Optional[str] = Field(None, min_length=1, max_length=50000)


class EmailTemplateListResponse(BaseResponse):
    """Response for listing email templates."""

    templates: list[EmailTemplateResponse]


# Available wildcards for templates
AVAILABLE_WILDCARDS = [
    {"name": "candidate_name", "description": "Candidate's first name"},
    {"name": "candidate_full_name", "description": "Candidate's full name"},
    {"name": "candidate_email", "description": "Candidate's email address"},
    {"name": "job_title", "description": "Job position title"},
    {"name": "company_name", "description": "Your company name"},
    {"name": "recruiter_name", "description": "Recruiter's name (you)"},
]


class WildcardsResponse(BaseResponse):
    """Available wildcards for email templates."""

    wildcards: list[dict]


# ========== Internal Endpoints (Called by Cloud Tasks) ==========


@internal_router.post(
    "/send",
    response_model=SendScheduledEmailResponse,
    summary="Send scheduled email (Internal)",
)
async def send_scheduled_email_internal(
    request: SendScheduledEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> SendScheduledEmailResponse:
    """Send a scheduled email. Called by Cloud Tasks at scheduled time."""
    email_service = EmailService(db)

    try:
        success = await email_service.send_scheduled_email(request.scheduled_email_id)

        message_id = None
        if success:
            stmt = select(ScheduledEmail).where(ScheduledEmail.id == request.scheduled_email_id)
            result = await db.execute(stmt)
            scheduled_email = result.scalar_one_or_none()
            if scheduled_email:
                message_id = scheduled_email.provider_message_id

        return SendScheduledEmailResponse(
            success=success,
            message="Email sent successfully" if success else "Failed to send email",
            message_id=message_id,
        )

    except Exception as e:
        logger.exception(f"Failed to send scheduled email {request.scheduled_email_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}",
        )


# ========== Email Sending Endpoints ==========


@email_router.post(
    "/applications/{application_id}/send-email",
    response_model=SendEmailResponse,
    summary="Send email to candidate",
)
async def send_email_to_application(
    application_id: UUID,
    request: SendEmailRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendEmailResponse:
    """Send an email to a candidate. Can be immediate or scheduled."""
    from sqlalchemy.orm import joinedload

    # Fetch application with job and company
    stmt = (
        select(Application)
        .options(joinedload(Application.job))
        .where(
            Application.id == application_id,
            Application.company_id == current_user["company_id"],
        )
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Render the email with wildcards
    template_renderer = TemplateRenderer()
    variables = {
        "candidate_name": application.first_name,
        "candidate_full_name": f"{application.first_name} {application.last_name}",
        "candidate_email": application.email,
        "job_title": application.job.title if application.job else "the position",
        "company_name": "Subtribe",  # TODO: Get from company record
        "recruiter_name": current_user.get("full_name", "The Team"),
    }
    fallbacks = {
        "candidate_name": "there",
        "job_title": "the position",
        "company_name": "our team",
    }

    rendered_subject = template_renderer.render_with_fallbacks(request.subject, variables, fallbacks)
    rendered_body = template_renderer.render_with_fallbacks(request.body, variables, fallbacks)

    email_service = EmailService(db)

    if request.send_immediately:
        # Send immediately
        scheduled_email = ScheduledEmail(
            company_id=current_user["company_id"],
            application_id=application_id,
            template_type="manual",
            recipient_email=application.email,
            recipient_name=f"{application.first_name} {application.last_name}",
            subject=rendered_subject,
            body=rendered_body,
            scheduled_for=datetime.now(timezone.utc),
            status="pending",
        )
        db.add(scheduled_email)
        await db.commit()
        await db.refresh(scheduled_email)

        # Send it
        success = await email_service.send_scheduled_email(scheduled_email.id)
        await db.refresh(scheduled_email)

        return SendEmailResponse(
            success=success,
            message="Email sent successfully" if success else "Failed to send email",
            email_id=scheduled_email.id,
            message_id=scheduled_email.provider_message_id,
        )
    else:
        # Schedule for later
        if not request.scheduled_for:
            raise HTTPException(status_code=400, detail="scheduled_for is required when not sending immediately")

        scheduled_email = ScheduledEmail(
            company_id=current_user["company_id"],
            application_id=application_id,
            template_type="manual",
            recipient_email=application.email,
            recipient_name=f"{application.first_name} {application.last_name}",
            subject=rendered_subject,
            body=rendered_body,
            scheduled_for=request.scheduled_for,
            status="pending",
        )
        db.add(scheduled_email)
        await db.commit()
        await db.refresh(scheduled_email)

        logger.info(f"📅 Scheduled email for {application.email} at {request.scheduled_for}")

        return SendEmailResponse(
            success=True,
            message=f"Email scheduled for {request.scheduled_for}",
            email_id=scheduled_email.id,
            scheduled_for=request.scheduled_for,
        )


@email_router.post(
    "/bulk-send",
    response_model=BulkEmailResponse,
    summary="Send bulk emails",
)
async def send_bulk_emails(
    request: BulkEmailRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BulkEmailResponse:
    """Send emails to multiple candidates at once."""
    from sqlalchemy.orm import joinedload

    # Fetch all applications
    stmt = (
        select(Application)
        .options(joinedload(Application.job))
        .where(
            Application.id.in_(request.application_ids),
            Application.company_id == current_user["company_id"],
        )
    )
    result = await db.execute(stmt)
    applications = result.scalars().unique().all()

    if not applications:
        raise HTTPException(status_code=404, detail="No applications found")

    template_renderer = TemplateRenderer()
    email_service = EmailService(db)
    scheduled_for = request.scheduled_for if not request.send_immediately else datetime.now(timezone.utc)

    successful = 0
    failed = 0
    email_ids = []

    for application in applications:
        try:
            # Render per-application
            variables = {
                "candidate_name": application.first_name,
                "candidate_full_name": f"{application.first_name} {application.last_name}",
                "candidate_email": application.email,
                "job_title": application.job.title if application.job else "the position",
                "company_name": "Subtribe",
                "recruiter_name": current_user.get("full_name", "The Team"),
            }
            fallbacks = {
                "candidate_name": "there",
                "job_title": "the position",
                "company_name": "our team",
            }

            rendered_subject = template_renderer.render_with_fallbacks(request.subject, variables, fallbacks)
            rendered_body = template_renderer.render_with_fallbacks(request.body, variables, fallbacks)

            scheduled_email = ScheduledEmail(
                company_id=current_user["company_id"],
                application_id=application.id,
                template_type="bulk",
                recipient_email=application.email,
                recipient_name=f"{application.first_name} {application.last_name}",
                subject=rendered_subject,
                body=rendered_body,
                scheduled_for=scheduled_for,
                status="pending",
            )
            db.add(scheduled_email)
            await db.flush()
            email_ids.append(scheduled_email.id)

            if request.send_immediately:
                success = await email_service.send_scheduled_email(scheduled_email.id)
                if success:
                    successful += 1
                else:
                    failed += 1
            else:
                successful += 1

        except Exception as e:
            logger.error(f"Failed to create email for application {application.id}: {e}")
            failed += 1

    await db.commit()

    return BulkEmailResponse(
        success=True,
        message=f"Processed {len(applications)} emails",
        total=len(applications),
        successful=successful,
        failed=failed,
        email_ids=email_ids,
    )


@email_router.post(
    "/applications/{application_id}/preview-email",
    response_model=PreviewEmailResponse,
    summary="Preview email",
)
async def preview_email(
    application_id: UUID,
    request: PreviewEmailRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewEmailResponse:
    """Preview what an email will look like with wildcards replaced."""
    from sqlalchemy.orm import joinedload

    # Fetch application
    stmt = (
        select(Application)
        .options(joinedload(Application.job))
        .where(
            Application.id == application_id,
            Application.company_id == current_user["company_id"],
        )
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Render with actual data
    template_renderer = TemplateRenderer()
    variables = {
        "candidate_name": application.first_name,
        "candidate_full_name": f"{application.first_name} {application.last_name}",
        "candidate_email": application.email,
        "job_title": application.job.title if application.job else "the position",
        "company_name": "Subtribe",
        "recruiter_name": current_user.get("full_name", "The Team"),
    }
    fallbacks = {
        "candidate_name": "there",
        "job_title": "the position",
        "company_name": "our team",
    }

    rendered_subject = template_renderer.render_with_fallbacks(request.subject, variables, fallbacks)
    rendered_body = template_renderer.render_with_fallbacks(request.body, variables, fallbacks)

    return PreviewEmailResponse(
        success=True,
        message="Preview generated",
        to_email=application.email,
        to_name=f"{application.first_name} {application.last_name}",
        subject=rendered_subject,
        body=rendered_body,
    )


@email_router.get(
    "/wildcards",
    response_model=WildcardsResponse,
    summary="Get available wildcards",
)
async def get_wildcards(
    current_user: dict = Depends(get_current_user),
) -> WildcardsResponse:
    """Get list of available wildcards for email templates."""
    return WildcardsResponse(
        success=True,
        message="Available wildcards",
        wildcards=AVAILABLE_WILDCARDS,
    )


# ========== Template Management Endpoints ==========


@router.get(
    "/templates",
    response_model=EmailTemplateListResponse,
    summary="List email templates",
)
async def list_email_templates(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateListResponse:
    """List all email templates for the company."""
    company_id = current_user["company_id"]

    stmt = select(EmailTemplate).where(EmailTemplate.company_id == company_id).order_by(EmailTemplate.name)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    return EmailTemplateListResponse(
        success=True,
        message=f"Found {len(templates)} templates",
        templates=[
            EmailTemplateResponse(
                id=t.id,
                name=t.name,
                template_type=t.template_type,
                category=t.category,
                subject=t.subject,
                body=t.body,
                wildcards=t.wildcards or [],
                is_default=t.is_default,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in templates
        ],
    )


@router.post(
    "/templates",
    response_model=EmailTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create email template",
)
async def create_email_template(
    request: CreateEmailTemplateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Create a new email template."""
    company_id = current_user["company_id"]

    # Check for duplicate name
    stmt = select(EmailTemplate).where(
        EmailTemplate.company_id == company_id,
        EmailTemplate.name == request.name,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template with this name already exists")

    # Extract wildcards from body
    import re
    wildcards_in_body = re.findall(r'\{(\w+)\}', request.body)
    wildcards_in_subject = re.findall(r'\{(\w+)\}', request.subject)
    all_wildcards = list(set(wildcards_in_body + wildcards_in_subject))

    template = EmailTemplate(
        company_id=company_id,
        name=request.name,
        template_type=request.category,  # For backwards compatibility
        category=request.category,
        subject=request.subject,
        body=request.body,
        wildcards=all_wildcards,
        is_default=False,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info(f"✨ Created template '{request.name}' for company {company_id}")

    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type,
        category=template.category,
        subject=template.subject,
        body=template.body,
        wildcards=template.wildcards or [],
        is_default=template.is_default,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.get(
    "/templates/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Get email template",
)
async def get_email_template(
    template_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Get a specific email template."""
    stmt = select(EmailTemplate).where(
        EmailTemplate.id == template_id,
        EmailTemplate.company_id == current_user["company_id"],
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type,
        category=template.category,
        subject=template.subject,
        body=template.body,
        wildcards=template.wildcards or [],
        is_default=template.is_default,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.put(
    "/templates/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Update email template",
)
async def update_email_template(
    template_id: UUID,
    request: UpdateEmailTemplateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Update an existing email template."""
    stmt = select(EmailTemplate).where(
        EmailTemplate.id == template_id,
        EmailTemplate.company_id == current_user["company_id"],
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Update fields if provided
    if request.name is not None:
        # Check for duplicate name
        check_stmt = select(EmailTemplate).where(
            EmailTemplate.company_id == current_user["company_id"],
            EmailTemplate.name == request.name,
            EmailTemplate.id != template_id,
        )
        check_result = await db.execute(check_stmt)
        if check_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Template with this name already exists")
        template.name = request.name

    if request.category is not None:
        template.category = request.category
        template.template_type = request.category

    if request.subject is not None:
        template.subject = request.subject

    if request.body is not None:
        template.body = request.body

    # Re-extract wildcards
    import re
    wildcards_in_body = re.findall(r'\{(\w+)\}', template.body)
    wildcards_in_subject = re.findall(r'\{(\w+)\}', template.subject)
    template.wildcards = list(set(wildcards_in_body + wildcards_in_subject))

    await db.commit()
    await db.refresh(template)

    logger.info(f"✏️ Updated template '{template.name}'")

    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type,
        category=template.category,
        subject=template.subject,
        body=template.body,
        wildcards=template.wildcards or [],
        is_default=template.is_default,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete email template",
)
async def delete_email_template(
    template_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    """Delete an email template."""
    stmt = select(EmailTemplate).where(
        EmailTemplate.id == template_id,
        EmailTemplate.company_id == current_user["company_id"],
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default template")

    template_name = template.name
    await db.delete(template)
    await db.commit()

    logger.info(f"🗑️ Deleted template '{template_name}'")

    return BaseResponse(success=True, message=f"Template '{template_name}' deleted")
