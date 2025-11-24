"""
Unit tests for services (with mocks).

Tests business logic without external dependencies.
"""

import io
from unittest.mock import MagicMock, patch

from app.services.storage import StorageService


class TestStorageService:
    """Test GCS storage service with mocks."""

    @patch("app.services.storage.service_account.Credentials.from_service_account_file")
    @patch("app.services.storage.storage.Client")
    def test_upload_resume_success(self, mock_storage_client, mock_credentials):
        """Test successful resume upload."""
        # Mock credentials
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds

        # Mock GCS client and bucket
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create storage service
        service = StorageService()
        service._client = mock_storage_client.return_value
        service._signing_credentials = mock_creds

        # Create fake file
        file_content = b"PDF content here"
        file_obj = io.BytesIO(file_content)

        # Upload resume (synchronous method)
        result = service.upload_resume(
            file=file_obj,
            company_id="company-123",
            job_id="job-456",
            application_id="app-789",
            full_name="John Doe",
            content_type="application/pdf",
        )

        # Verify upload was called
        mock_blob.upload_from_file.assert_called_once()

        # Verify result is GCS URI
        assert result.startswith("gs://")
        assert "company-123" in result
        assert "job-456" in result

    @patch("app.services.storage.service_account.Credentials.from_service_account_file")
    @patch("app.services.storage.storage.Client")
    def test_generate_signed_url_inline(self, mock_storage_client, mock_credentials):
        """Test generating signed URL for viewing (inline)."""
        # Mock credentials
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds

        # Mock GCS client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"

        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create storage service
        service = StorageService()
        service._client = mock_storage_client.return_value
        service._signing_credentials = mock_creds

        # Generate signed URL (synchronous method)
        result = service.generate_signed_url(
            gcs_uri="gs://bucket/path/to/resume.pdf",
            disposition="inline",
        )

        # Verify signed URL was generated
        mock_blob.generate_signed_url.assert_called_once()
        assert result == "https://storage.googleapis.com/signed-url"

        # Verify inline content disposition
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["response_disposition"].startswith("inline")

    @patch("app.services.storage.service_account.Credentials.from_service_account_file")
    @patch("app.services.storage.storage.Client")
    def test_generate_signed_url_attachment(self, mock_storage_client, mock_credentials):
        """Test generating signed URL for download (attachment)."""
        # Mock credentials
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds

        # Mock GCS client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"

        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create storage service
        service = StorageService()
        service._client = mock_storage_client.return_value
        service._signing_credentials = mock_creds

        # Generate signed URL (synchronous method)
        service.generate_signed_url(
            gcs_uri="gs://bucket/path/to/resume.pdf",
            disposition="attachment",
        )

        # Verify attachment content disposition
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["response_disposition"].startswith("attachment")

    def test_generate_path(self):
        """Test generating blob path with correct format."""
        service = StorageService()

        path = service.generate_path(
            company_id="company-123",
            job_id="job-456",
            application_id="app-789",
            full_name="John Doe",
            extension="pdf",
        )

        # Verify format: company_id/job_id/app_id_timestamp_name.ext
        assert path.startswith("company-123/job-456/app-789_")
        assert path.endswith(".pdf")
        assert "john_doe" in path

        # Verify timestamp is included
        parts = path.split("_")
        assert len(parts) >= 3  # app-id, timestamp, name
