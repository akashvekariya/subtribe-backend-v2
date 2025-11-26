"""Email providers package."""

from app.email.providers.base import EmailMessage, EmailProvider, EmailResult
from app.email.providers.sendgrid_provider import SendGridEmailProvider
from app.email.providers.stub import StubEmailProvider

__all__ = [
    "EmailProvider",
    "EmailMessage",
    "EmailResult",
    "StubEmailProvider",
    "SendGridEmailProvider",
]
