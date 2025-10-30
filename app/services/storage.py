"""Google Cloud Storage service for resume uploads."""

import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import BinaryIO

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file uploads to Google Cloud Storage."""

    def __init__(self):
        """Initialize GCS client and bucket.

        Authentication:
        - Local: Uses service account key file via GOOGLE_APPLICATION_CREDENTIALS
        - Cloud Run: Uses Application Default Credentials (attached service account)

        For signed URL generation on Cloud Run, the service account must have:
        - roles/iam.serviceAccountTokenCreator (for IAM-based signing without private key)
        """
        # Set GCS credentials from environment (skip if /dev/null or doesn't exist)
        # In Cloud Run, credentials come from the service account automatically (ADC)
        creds_path = settings.google_application_credentials
        if creds_path and creds_path != "/dev/null" and os.path.exists(creds_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

        self._client: storage.Client | None = None
        self._bucket: storage.Bucket | None = None

    @property
    def client(self) -> storage.Client:
        """Lazy-load GCS client.

        Uses Application Default Credentials which automatically discovers credentials from:
        - GOOGLE_APPLICATION_CREDENTIALS env var (local development with key file)
        - Metadata server (Cloud Run with attached service account)
        """
        if self._client is None:
            self._client = storage.Client(project=settings.gcs_project_id)
        return self._client

    @property
    def bucket(self) -> storage.Bucket:
        """Lazy-load GCS bucket."""
        if self._bucket is None:
            self._bucket = self.client.bucket(settings.gcs_bucket_name)
        return self._bucket

    def sanitize_filename(self, name: str, max_length: int = 50) -> str:
        """
        Convert name to safe filename.

        Args:
            name: Original name (e.g., "John Doe")
            max_length: Maximum length of sanitized name

        Returns:
            Sanitized filename (e.g., "john_doe")
        """
        # Normalize unicode characters
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")

        # Convert to lowercase and replace spaces
        name = name.lower().replace(" ", "_")

        # Remove non-alphanumeric characters (keep underscores)
        name = re.sub(r"[^a-z0-9_]", "", name)

        # Remove multiple underscores and trim
        name = re.sub(r"_+", "_", name).strip("_")

        return name[:max_length] if name else "resume"

    def generate_path(
        self,
        company_id: str,
        job_id: str,
        application_id: str,
        full_name: str,
        extension: str = "pdf",
    ) -> str:
        """
        Generate GCS path for resume.

        Format: {company_id}/{job_id}/{app_id}_{timestamp}_{name}.{ext}
        Example: abc123/def456/ghi789_1696598400_john_doe.pdf

        Args:
            company_id: Company UUID
            job_id: Job UUID
            application_id: Application UUID
            full_name: Candidate's full name
            extension: File extension (pdf or docx)

        Returns:
            GCS path string
        """
        timestamp = int(datetime.now(timezone.utc).timestamp())
        sanitized_name = self.sanitize_filename(full_name)
        filename = f"{application_id}_{timestamp}_{sanitized_name}.{extension}"
        return f"{company_id}/{job_id}/{filename}"

    def upload_resume(
        self,
        file: BinaryIO,
        company_id: str,
        job_id: str,
        application_id: str,
        full_name: str,
        content_type: str,
    ) -> str:
        """
        Upload resume file to GCS.

        Args:
            file: File-like object to upload
            company_id: Company UUID
            job_id: Job UUID
            application_id: Application UUID
            full_name: Candidate's full name (for filename)
            content_type: MIME type (e.g., "application/pdf")

        Returns:
            GCS URI (gs://bucket-name/path/to/file.pdf)

        Raises:
            GoogleCloudError: If upload fails
        """
        try:
            # Determine file extension
            extension = "pdf" if "pdf" in content_type.lower() else "docx"

            # Generate storage path
            path = self.generate_path(
                company_id=company_id,
                job_id=job_id,
                application_id=application_id,
                full_name=full_name,
                extension=extension,
            )

            # Upload to GCS
            blob = self.bucket.blob(path)
            blob.upload_from_file(file, content_type=content_type, timeout=60)

            logger.info(f"Uploaded resume to GCS: {path}")

            # Return GCS URI
            return f"gs://{self.bucket.name}/{path}"

        except Exception as e:
            logger.error(f"Failed to upload resume: {str(e)}")
            raise GoogleCloudError(f"Failed to upload file: {str(e)}") from e

    def generate_signed_url(
        self, gcs_uri: str, expiration_minutes: int = 60, disposition: str = "inline"
    ) -> str:
        """
        Generate temporary signed URL for accessing file.

        Works in both environments:
        - Local: Uses service account key file (private key signing)
        - Cloud Run: Uses IAM signBlob API (requires roles/iam.serviceAccountTokenCreator)

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file.pdf)
            expiration_minutes: URL expiry time in minutes
            disposition: "inline" (view in browser) or "attachment" (download)

        Returns:
            Signed URL (valid for specified duration)

        Raises:
            GoogleCloudError: If URL generation fails
        """
        try:
            # Extract path from GCS URI
            path = gcs_uri.replace(f"gs://{self.bucket.name}/", "")
            blob = self.bucket.blob(path)
            filename = path.split("/")[-1]

            # Get credentials to determine signing method
            client_creds = self.client._credentials

            # Check if credentials have signing capability (private key)
            has_private_key = hasattr(client_creds, "sign_bytes")

            if has_private_key:
                # Local: Use private key signing (service account key file)
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET",
                    response_disposition=f'{disposition}; filename="{filename}"',
                )
                logger.info(f"Generated signed URL using private key for: {path}")
            else:
                # Cloud Run: Use IAM signBlob API
                # When service_account_email is provided without access_token,
                # the library uses IAM Credentials API to sign the blob

                # Get service account email from the running environment
                # This is set via --service-account in Cloud Run deployment
                if (
                    hasattr(client_creds, "service_account_email")
                    and client_creds.service_account_email
                ):
                    service_account_email = client_creds.service_account_email
                else:
                    # Fallback: Fetch from metadata server (Cloud Run/GCE)
                    try:
                        import requests as http_requests

                        resp = http_requests.get(
                            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
                            headers={"Metadata-Flavor": "Google"},
                            timeout=2,
                        )
                        service_account_email = resp.text.strip()
                    except Exception as e:
                        logger.error(f"Failed to get service account email: {e}")
                        raise GoogleCloudError(
                            "Unable to determine service account for signing"
                        ) from e

                # Generate signed URL using IAM signing
                # Library automatically calls IAM signBlob API when:
                # 1. service_account_email is provided
                # 2. credentials don't have private key (compute credentials)
                # 3. Service account has iam.serviceAccountTokenCreator permission
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET",
                    response_disposition=f'{disposition}; filename="{filename}"',
                    service_account_email=service_account_email,
                )
                logger.info(
                    f"Generated signed URL using IAM signBlob API for: {path} | SA: {service_account_email}"
                )

            return url

        except Exception as e:
            # Single-line structured logging for better debugging
            error_msg = str(e).replace("\n", " ").replace("  ", " ")
            logger.error(
                f"Failed to generate signed URL | Path: {path} | Error: {error_msg}",
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to generate download URL: {str(e)}") from e

    def get_resume_view_url(self, gcs_uri: str) -> str:
        """
        Generate signed URL for viewing resume in browser.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file.pdf)

        Returns:
            Signed URL with inline disposition (opens in browser)
        """
        return self.generate_signed_url(gcs_uri, expiration_minutes=60, disposition="inline")

    def get_resume_download_url(self, gcs_uri: str) -> str:
        """
        Generate signed URL for downloading resume.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file.pdf)

        Returns:
            Signed URL with attachment disposition (forces download)
        """
        return self.generate_signed_url(gcs_uri, expiration_minutes=60, disposition="attachment")


# Singleton instance
storage_service = StorageService()
