"""Default email templates for interview invites and rejections."""

from __future__ import annotations

# Default templates use {variable_name} syntax for substitution
# Available variables:
# - candidate_name: Candidate's first name (or "there" as fallback)
# - company_name: Company name
# - job_title: Job position title

DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "interview_invite": {
        "subject": "Interview Invitation - {job_title} at {company_name}",
        "body": """Hey {candidate_name},

Thank you for applying to the {job_title} position at {company_name}!

We've reviewed your application and would like to invite you to the next round of our hiring process.

We'll reach out to you shortly to coordinate a convenient time for the interview.

We look forward to speaking with you soon!

Best regards,
{company_name} Hiring Team

---
This is an automated message from Subtribe. Please do not reply directly to this email.""",
    },
    "rejection": {
        "subject": "Update on Your Application - {job_title} at {company_name}",
        "body": """Hey {candidate_name},

Thank you for taking the time to apply for the {job_title} position at {company_name}.

After careful consideration, we have decided to move forward with other candidates whose experience more closely aligns with our current needs.

We appreciate your interest in {company_name} and encourage you to apply for future opportunities that match your skills and experience.

We wish you the best in your job search.

Best regards,
{company_name} Hiring Team

---
This is an automated message from Subtribe. Please do not reply directly to this email.""",
    },
}


def get_default_template(template_type: str) -> dict[str, str]:
    """Get default template for the given type.

    Args:
        template_type: Either 'interview_invite' or 'rejection'

    Returns:
        Dictionary with 'subject' and 'body' keys

    Raises:
        ValueError: If template_type is invalid
    """
    if template_type not in DEFAULT_TEMPLATES:
        raise ValueError(
            f"Invalid template_type: {template_type}. "
            f"Must be one of {list(DEFAULT_TEMPLATES.keys())}"
        )

    return DEFAULT_TEMPLATES[template_type].copy()


def get_required_variables(template_type: str) -> list[str]:
    """Get list of required variables for the template type.

    Args:
        template_type: Either 'interview_invite' or 'rejection'

    Returns:
        List of required variable names
    """
    base_vars = ["candidate_name", "company_name", "job_title"]

    if template_type == "interview_invite" or template_type == "rejection":
        return base_vars
    else:
        raise ValueError(f"Invalid template_type: {template_type}")


def get_variable_fallbacks() -> dict[str, str]:
    """Get fallback values for template variables.

    Returns:
        Dictionary of variable_name -> fallback_value
    """
    return {
        "candidate_name": "there",  # "Hey there" instead of "Hey {name}"
        "company_name": "our team",
        "job_title": "the position",
    }
