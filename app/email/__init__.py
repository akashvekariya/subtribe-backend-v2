"""Email service module for scheduled email delivery."""

from app.email.providers import (
    EmailMessage,
    EmailProvider,
    EmailResult,
    SendGridEmailProvider,
    StubEmailProvider,
)

__all__ = [
    "EmailProvider",
    "EmailMessage",
    "EmailResult",
    "StubEmailProvider",
    "SendGridEmailProvider",
]
