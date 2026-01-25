"""Authentication service - business logic for user authentication."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    generate_password_reset_token,
    generate_verification_token,
    hash_password,
    mask_email,
    verify_password,
)
from app.email.providers import EmailMessage, SendGridEmailProvider, StubEmailProvider
from app.models.company import Company
from app.models.invite import Invite
from app.models.user import User
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Security constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
VERIFICATION_TOKEN_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1


@dataclass
class AuthResult:
    """Result of authentication operations."""

    user: User
    company: Company | None
    access_token: str
    expires_at: datetime


@dataclass
class ClaimInviteResult:
    """Result of claiming an invite."""

    user: User
    company: Company | None
    invite_type: str
    redirect_to: str
    message: str
    access_token: str


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_email_provider(self):
        """Get configured email provider."""
        if not settings.email_enabled or settings.email_provider == "stub":
            return StubEmailProvider()
        return SendGridEmailProvider(
            api_key=settings.sendgrid_api_key,
            sandbox_mode=settings.sendgrid_sandbox_mode,
        )

    async def _send_email(self, message: EmailMessage) -> bool:
        """Send email using configured provider."""
        provider = self._get_email_provider()
        result = await provider.send_email(message)
        return result.success

    async def send_verification_email(self, user: User, token: str) -> bool:
        """Send email verification email."""
        verification_url = f"{settings.dashboard_url}/verify-email/{token}"

        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Verify your Subtribe account",
            body=f"""Hi {user.first_name},

Please verify your email address to complete your Subtribe registration.

Click the link below to verify:
{verification_url}

This link expires in {VERIFICATION_TOKEN_EXPIRY_HOURS} hours.

If you didn't create this account, you can ignore this email.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        success = await self._send_email(message)

        if success:
            logger.info(f"Verification email sent to {user.email}")
        else:
            logger.error(f"Failed to send verification email to {user.email}")

        return success

    async def send_password_reset_email(self, user: User, token: str) -> bool:
        """Send password reset email to user."""
        reset_url = f"{settings.dashboard_url}/reset-password/{token}"

        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Reset Your Subtribe Password",
            body=f"""Hi {user.first_name},

We received a request to reset your password for your Subtribe account.

Click the link below to reset your password:
{reset_url}

This link will expire in {PASSWORD_RESET_EXPIRY_HOURS} hour.

If you didn't request this, you can safely ignore this email.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        success = await self._send_email(message)

        if success:
            logger.info(f"Password reset email sent to {user.email}")
        else:
            logger.error(f"Failed to send password reset email to {user.email}")

        return success

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_company_by_id(self, company_id: UUID) -> Company | None:
        """Get company by ID."""
        stmt = select(Company).where(Company.id == company_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def register(
        self, email: str, password: str, first_name: str, last_name: str
    ) -> AuthResult:
        """
        Register a new user.

        Returns AuthResult with user, access token, and expiry.
        Raises ConflictError if email already exists.
        """
        # Check if email already exists
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise ConflictError(message="Email already registered", code="duplicate_email")

        # Hash password
        password_hash = hash_password(password)

        # Generate verification token
        verification_token = generate_verification_token()
        verification_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=VERIFICATION_TOKEN_EXPIRY_HOURS
        )

        # Create user WITHOUT company
        user = User(
            company_id=None,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role="admin",
            is_active=True,
            email_verified=False,
            pending_onboarding=False,
            email_verification_token=verification_token,
            email_verification_expires_at=verification_expires_at,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Send verification email (don't fail registration if email fails)
        await self.send_verification_email(user, verification_token)

        # Create JWT
        access_token, expires_at = create_access_token(
            user_id=str(user.id),
            company_id=None,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            email_verified=False,
        )

        return AuthResult(user=user, company=None, access_token=access_token, expires_at=expires_at)

    async def login(self, email: str, password: str, client_ip: str | None = None) -> AuthResult:
        """
        Authenticate user with email and password.

        Implements account lockout after MAX_FAILED_ATTEMPTS.
        Returns AuthResult with user, company, access token, and expiry.
        Raises UnauthorizedError on failure.
        """
        user = await self.get_user_by_email(email)

        if not user:
            raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

        # Check if account is locked
        if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
            minutes_remaining = int(
                (user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60
            )
            raise UnauthorizedError(
                message=f"Account is temporarily locked. Try again in {minutes_remaining + 1} minutes.",
                code="account_locked",
            )

        # Clear expired lockout
        if user.locked_until and datetime.now(timezone.utc) >= user.locked_until:
            user.locked_until = None
            user.failed_login_attempts = 0

        # Verify password
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

            # Lock account after max attempts
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                await self.db.commit()
                logger.warning(f"Account locked due to failed login attempts: {user.email}")

                # Send security alert
                await notification_service.send_account_locked_alert(
                    user, lockout_minutes=LOCKOUT_DURATION_MINUTES, ip_address=client_ip
                )

                raise UnauthorizedError(
                    message=f"Account locked due to too many failed attempts. "
                    f"Try again in {LOCKOUT_DURATION_MINUTES} minutes.",
                    code="account_locked",
                )

            await self.db.commit()
            remaining = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
            logger.info(f"Failed login attempt for {user.email}. {remaining} attempts remaining.")
            raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

        if not user.is_active:
            raise UnauthorizedError(message="Account is inactive", code="account_inactive")

        # Get company if user has one
        company = None
        if user.company_id:
            company = await self.get_company_by_id(user.company_id)
            if company and not company.is_active:
                raise UnauthorizedError(
                    message="Organization is not active", code="company_inactive"
                )

        # Successful login - reset failed attempts and update tracking
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = client_ip
        await self.db.commit()

        # Create JWT
        access_token, expires_at = create_access_token(
            user_id=str(user.id),
            company_id=str(company.id) if company else None,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            email_verified=user.email_verified,
        )

        return AuthResult(
            user=user, company=company, access_token=access_token, expires_at=expires_at
        )

    async def verify_email(self, token: str) -> tuple[bool, str]:
        """
        Verify email using token.

        Returns (success, message).
        Raises NotFoundError if token invalid, ValidationError if expired.
        """
        stmt = select(User).where(User.email_verification_token == token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(message="Invalid verification token", code="invalid_token")

        if user.email_verified:
            return True, "Email already verified"

        # Check if token expired
        if (
            user.email_verification_expires_at
            and datetime.now(timezone.utc) > user.email_verification_expires_at
        ):
            raise ValidationError(
                message="Verification token has expired. Please request a new one.",
                code="token_expired",
            )

        # Mark email as verified
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.email_verification_token = None
        user.email_verification_expires_at = None

        await self.db.commit()
        logger.info(f"Email verified for user {user.email}")

        return True, "Email verified successfully"

    async def resend_verification(self, email: str) -> tuple[bool, str]:
        """
        Resend verification email.

        Returns (success, message). Always returns success to prevent email enumeration.
        """
        user = await self.get_user_by_email(email)

        if not user:
            return True, "If the email exists, a verification link has been sent."

        if user.email_verified:
            return True, "Email is already verified."

        # Generate new verification token
        verification_token = generate_verification_token()
        user.email_verification_token = verification_token
        user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=VERIFICATION_TOKEN_EXPIRY_HOURS
        )

        await self.db.commit()

        # Send verification email
        await self.send_verification_email(user, verification_token)

        return True, "If the email exists, a verification link has been sent."

    async def request_password_reset(self, email: str) -> bool:
        """
        Request password reset.

        Returns True always to prevent email enumeration.
        """
        user = await self.get_user_by_email(email)

        if not user:
            logger.info(f"Password reset requested for non-existent email: {email}")
            return True

        if not user.is_active:
            logger.info(f"Password reset requested for inactive account: {email}")
            return True

        # Generate reset token
        reset_token = generate_password_reset_token()
        user.password_reset_token = reset_token
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=PASSWORD_RESET_EXPIRY_HOURS
        )
        user.password_reset_requested_at = datetime.now(timezone.utc)

        await self.db.commit()

        # Send email
        await self.send_password_reset_email(user, reset_token)

        return True

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using token.

        Returns True on success.
        Raises ValidationError on invalid/expired token.
        """
        stmt = select(User).where(User.password_reset_token == token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValidationError(
                message="Invalid or expired password reset token",
                code="invalid_reset_token",
            )

        # Check if token expired
        if (
            user.password_reset_expires_at
            and datetime.now(timezone.utc) > user.password_reset_expires_at
        ):
            user.password_reset_token = None
            user.password_reset_expires_at = None
            await self.db.commit()

            raise ValidationError(
                message="Password reset token has expired. Please request a new one.",
                code="token_expired",
            )

        if not user.is_active:
            raise ValidationError(message="Account is inactive", code="account_inactive")

        # Update password
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires_at = None
        user.password_reset_requested_at = None
        user.last_password_change = datetime.now(timezone.utc)

        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None

        await self.db.commit()
        logger.info(f"Password reset successful for user {user.email}")

        # Send success notification
        await notification_service.send_password_reset_success(user)

        return True

    async def validate_reset_token(self, token: str) -> tuple[bool, str | None, str | None]:
        """
        Validate password reset token.

        Returns (valid, masked_email, message).
        """
        stmt = select(User).where(User.password_reset_token == token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False, None, "Invalid or expired password reset token"

        if (
            user.password_reset_expires_at
            and datetime.now(timezone.utc) > user.password_reset_expires_at
        ):
            return False, None, "Password reset token has expired. Please request a new one."

        if not user.is_active:
            return False, None, "Account is inactive"

        return True, mask_email(user.email), None

    async def claim_invite(self, user_id: UUID, invite_code: str) -> ClaimInviteResult:
        """
        Claim an invite code.

        Returns ClaimInviteResult with user, company, redirect info.
        Raises various errors on failure.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found", code="user_not_found")

        if user.company_id:
            raise ValidationError(
                message="You are already part of an organization",
                code="already_has_company",
            )

        # Get invite
        stmt = select(Invite).where(Invite.code == invite_code)
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            raise NotFoundError(message="Invalid invite code", code="invalid_invite")

        # Verify email match
        if invite.email and invite.email.lower() != user.email.lower():
            logger.warning(
                f"Invite claim attempt with email mismatch: invite={invite.email}, user={user.email}"
            )
            raise ValidationError(message="Invalid invite code", code="email_mismatch")

        # Check validity
        if not invite.is_valid:
            if invite.expires_at and datetime.now(timezone.utc) > invite.expires_at:
                raise ValidationError(message="Invite code has expired", code="invite_expired")
            if invite.max_uses and invite.uses_count >= invite.max_uses:
                raise ValidationError(
                    message="Invite code has reached maximum uses", code="invite_maxed"
                )
            raise ValidationError(message="Invite code is no longer active", code="invite_inactive")

        # Handle based on invite type
        company = None
        redirect_to = "/"

        if invite.invite_type == "org_creator":
            user.pending_onboarding = True
            redirect_to = "/onboarding"
            message = "Invite claimed. Please complete organization setup."
        else:
            if not invite.company_id:
                raise ValidationError(
                    message="Invalid invite configuration", code="invalid_invite_config"
                )

            company = await self.get_company_by_id(invite.company_id)
            if not company or not company.is_active:
                raise ValidationError(message="Organization is not active", code="company_inactive")

            user.company_id = company.id
            user.pending_onboarding = False
            redirect_to = "/"
            message = f"Welcome to {company.name}!"

        # Increment invite usage
        invite.uses_count += 1

        await self.db.commit()
        await self.db.refresh(user)

        # Create new JWT
        access_token, _ = create_access_token(
            user_id=str(user.id),
            company_id=str(company.id) if company else None,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            email_verified=user.email_verified,
        )

        return ClaimInviteResult(
            user=user,
            company=company,
            invite_type=invite.invite_type,
            redirect_to=redirect_to,
            message=message,
            access_token=access_token,
        )

    async def get_user_with_company(self, user_id: UUID) -> tuple[User | None, Company | None]:
        """Get user and their company if they have one."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None, None

        company = None
        if user.company_id:
            company = await self.get_company_by_id(user.company_id)

        return user, company
