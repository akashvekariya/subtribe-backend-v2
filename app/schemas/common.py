"""Common schemas - Shared models used across multiple modules."""

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    """Pagination metadata for paginated list responses.

    Follows industry-standard pagination format with offset-based approach.
    Used consistently across all paginated endpoints.
    """

    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    limit: int = Field(..., ge=1, le=100, description="Number of items per page")
    total: int = Field(..., ge=0, description="Total number of items across all pages")
    total_pages: int = Field(..., ge=0, description="Total number of pages available")
    has_more: bool = Field(..., description="Whether more pages are available")
