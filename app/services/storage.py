"""Google Cloud Storage service for resume uploads."""

import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import BinaryIO

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from google.oauth2 import service_account

from app.core.config import settings
from app.core.dependencies import get_correlation_id

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file uploads to Google Cloud Storage."""

    def __init__(self):
        """Initialize GCS client and bucket.

        Authentication:
        - Uses service account key file for ALL operations (upload + signed URLs)
        - Key file must have Storage Object Admin + Storage Object Creator roles
        """
        self._client: storage.Client | None = None
        self._bucket: storage.Bucket | None = None
        self._signing_credentials: service_account.Credentials | None = None

    def _get_credentials(self) -> service_account.Credentials:
        """Load service account credentials from key file.

        Returns:
            Service account credentials with private key for signing
        """
        if self._signing_credentials is None:
            creds_path = settings.google_application_credentials

            # Check if credentials path exists and is valid
            if not creds_path or creds_path == "/dev/null" or not os.path.exists(creds_path):
                raise ValueError(
                    f"Invalid or missing service account key file: {creds_path}. "
                    "Set GOOGLE_APPLICATION_CREDENTIALS to valid JSON key file path."
                )

            # Load service account credentials from JSON key file
            self._signing_credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            logger.info(
                "Service account credentials loaded",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "credentials_loaded",
                    "credentials_path": creds_path,
                },
            )

        return self._signing_credentials

    @property
    def client(self) -> storage.Client:
        """Lazy-load GCS client with service account credentials."""
        if self._client is None:
            credentials = self._get_credentials()
            self._client = storage.Client(
                project=settings.gcs_project_id,
                credentials=credentials,
            )
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
        start_time = time.time()
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

            duration_ms = int((time.time() - start_time) * 1000)
            gcs_uri = f"gs://{self.bucket.name}/{path}"

            logger.info(
                "Resume uploaded to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "resume_upload",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                    "company_id": company_id,
                    "job_id": job_id,
                    "application_id": application_id,
                    "content_type": content_type,
                },
            )

            # Return GCS URI
            return gcs_uri

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Failed to upload resume to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "resume_upload",
                    "duration_ms": duration_ms,
                    "success": False,
                    "error": str(e),
                    "company_id": company_id,
                    "job_id": job_id,
                    "application_id": application_id,
                },
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to upload file: {str(e)}") from e

    def generate_signed_url(
        self, gcs_uri: str, expiration_minutes: int = 60, disposition: str = "inline"
    ) -> str:
        """
        Generate temporary signed URL for accessing file.

        Uses service account credentials with private key for signing.
        Works in both local and Cloud Run environments (requires key file).

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file.pdf)
            expiration_minutes: URL expiry time in minutes
            disposition: "inline" (view in browser) or "attachment" (download)

        Returns:
            Signed URL (valid for specified duration)

        Raises:
            GoogleCloudError: If URL generation fails
        """
        start_time = time.time()
        try:
            # Extract path from GCS URI
            path = gcs_uri.replace(f"gs://{self.bucket.name}/", "")
            blob = self.bucket.blob(path)
            filename = path.split("/")[-1]

            # Generate signed URL using service account private key
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
                response_disposition=f'{disposition}; filename="{filename}"',
                credentials=self._get_credentials(),
            )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Generated signed URL for GCS file",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "generate_signed_url",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                    "disposition": disposition,
                    "expiration_minutes": expiration_minutes,
                },
            )
            return url

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e).replace("\n", " ").replace("  ", " ")
            path_str = path if "path" in locals() else gcs_uri

            logger.error(
                "Failed to generate signed URL",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "generate_signed_url",
                    "duration_ms": duration_ms,
                    "success": False,
                    "gcs_uri": gcs_uri,
                    "path": path_str,
                    "error": error_msg,
                },
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

    def upload_temp_zip(self, file: BinaryIO, company_id: str, batch_id: str) -> str:
        """
        Upload ZIP file to temporary location for bulk upload processing.

        Args:
            file: File-like object containing the ZIP
            company_id: Company UUID
            batch_id: Bulk upload batch UUID

        Returns:
            GCS URI (gs://bucket-name/temp/company_id/bulk_uploads/batch_id.zip)

        Raises:
            GoogleCloudError: If upload fails
        """
        start_time = time.time()
        try:
            path = f"temp/{company_id}/bulk_uploads/{batch_id}.zip"
            blob = self.bucket.blob(path)
            blob.upload_from_file(file, content_type="application/zip", timeout=300)

            duration_ms = int((time.time() - start_time) * 1000)
            gcs_uri = f"gs://{self.bucket.name}/{path}"

            logger.info(
                "Temp ZIP uploaded to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "temp_zip_upload",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                    "company_id": company_id,
                    "batch_id": batch_id,
                },
            )

            return gcs_uri

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Failed to upload temp ZIP to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "temp_zip_upload",
                    "duration_ms": duration_ms,
                    "success": False,
                    "error": str(e),
                    "company_id": company_id,
                    "batch_id": batch_id,
                },
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to upload temp ZIP: {str(e)}") from e

    def upload_file_bytes(
        self,
        content: bytes,
        path: str,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Upload file bytes to a specific GCS path.

        Args:
            content: File contents as bytes
            path: Full GCS path (without bucket prefix)
            content_type: MIME type

        Returns:
            GCS URI (gs://bucket-name/path)

        Raises:
            GoogleCloudError: If upload fails
        """
        start_time = time.time()
        try:
            blob = self.bucket.blob(path)
            blob.upload_from_string(content, content_type=content_type, timeout=60)

            duration_ms = int((time.time() - start_time) * 1000)
            gcs_uri = f"gs://{self.bucket.name}/{path}"

            logger.info(
                "File bytes uploaded to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "file_bytes_upload",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                    "size_bytes": len(content),
                },
            )

            return gcs_uri

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Failed to upload file bytes to GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "file_bytes_upload",
                    "duration_ms": duration_ms,
                    "success": False,
                    "error": str(e),
                    "path": path,
                },
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to upload file: {str(e)}") from e

    def delete_file(self, gcs_uri: str) -> bool:
        """
        Delete file from GCS.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file)

        Returns:
            True if deleted successfully

        Raises:
            GoogleCloudError: If deletion fails
        """
        start_time = time.time()
        try:
            # Parse bucket and path from GCS URI
            if not gcs_uri.startswith("gs://"):
                raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

            uri_without_prefix = gcs_uri[5:]  # Remove "gs://"
            parts = uri_without_prefix.split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

            bucket_name = parts[0]
            path = parts[1]

            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(path)
            blob.delete(timeout=30)

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "File deleted from GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "delete_file",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                },
            )
            return True

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Failed to delete file from GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "delete_file",
                    "duration_ms": duration_ms,
                    "success": False,
                    "gcs_uri": gcs_uri,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to delete file: {str(e)}") from e

    def download_file(self, gcs_uri: str) -> bytes:
        """
        Download file contents from GCS.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/to/file.pdf)

        Returns:
            File contents as bytes

        Raises:
            GoogleCloudError: If download fails
        """
        start_time = time.time()
        try:
            # Parse bucket and path from GCS URI
            # Format: gs://bucket-name/path/to/file.pdf
            if not gcs_uri.startswith("gs://"):
                raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

            uri_without_prefix = gcs_uri[5:]  # Remove "gs://"
            parts = uri_without_prefix.split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

            bucket_name = parts[0]
            path = parts[1]

            # Get the bucket (may be different from default)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(path)

            # Download to bytes
            contents = blob.download_as_bytes(timeout=60)

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Downloaded file from GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "download_file",
                    "duration_ms": duration_ms,
                    "success": True,
                    "gcs_uri": gcs_uri,
                    "size_bytes": len(contents),
                },
            )
            return contents

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Failed to download file from GCS",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "external_service",
                    "service": "gcs",
                    "operation": "download_file",
                    "duration_ms": duration_ms,
                    "success": False,
                    "gcs_uri": gcs_uri,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise GoogleCloudError(f"Failed to download file: {str(e)}") from e


# Singleton instance
storage_service = StorageService()
