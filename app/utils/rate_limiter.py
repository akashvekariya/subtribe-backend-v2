"""Simple in-memory rate limiter for password reset requests.

This is a basic implementation suitable for single-instance deployments.
For production with multiple instances, consider Redis-based rate limiting.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock


@dataclass
class RateLimitEntry:
    """Stores rate limit data for a key."""

    count: int
    first_request_time: float


class InMemoryRateLimiter:
    """Simple in-memory rate limiter with sliding window.

    Rate limits requests per key (e.g., email address) within a time window.
    Thread-safe implementation using locks.

    Example:
        limiter = InMemoryRateLimiter(max_requests=3, window_seconds=3600)

        # Check if request is allowed
        if not limiter.is_allowed("user@example.com"):
            raise RateLimitError("Too many requests")

        # Record the request
        limiter.record("user@example.com")
    """

    def __init__(self, max_requests: int = 3, window_seconds: int = 3600):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed within the window.
            window_seconds: Time window in seconds (default: 1 hour).
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._entries: dict[str, RateLimitEntry] = defaultdict(
            lambda: RateLimitEntry(count=0, first_request_time=0)
        )
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key.

        Args:
            key: Identifier for rate limiting (e.g., email address).

        Returns:
            True if request is allowed, False if rate limited.
        """
        with self._lock:
            current_time = time.time()
            entry = self._entries[key]

            # Reset window if expired
            if current_time - entry.first_request_time > self.window_seconds:
                entry.count = 0
                entry.first_request_time = current_time

            return entry.count < self.max_requests

    def record(self, key: str) -> None:
        """Record a request for the given key.

        Args:
            key: Identifier for rate limiting (e.g., email address).
        """
        with self._lock:
            current_time = time.time()
            entry = self._entries[key]

            # Reset window if expired
            if current_time - entry.first_request_time > self.window_seconds:
                entry.count = 1
                entry.first_request_time = current_time
            else:
                entry.count += 1

    def get_remaining(self, key: str) -> int:
        """Get remaining requests allowed for the key.

        Args:
            key: Identifier for rate limiting.

        Returns:
            Number of remaining requests in current window.
        """
        with self._lock:
            current_time = time.time()
            entry = self._entries[key]

            # Window expired - full quota available
            if current_time - entry.first_request_time > self.window_seconds:
                return self.max_requests

            return max(0, self.max_requests - entry.count)

    def get_reset_time(self, key: str) -> float:
        """Get time until rate limit resets.

        Args:
            key: Identifier for rate limiting.

        Returns:
            Seconds until the window resets. Returns 0 if not rate limited.
        """
        with self._lock:
            current_time = time.time()
            entry = self._entries[key]

            if entry.count == 0:
                return 0

            time_elapsed = current_time - entry.first_request_time
            time_remaining = self.window_seconds - time_elapsed

            return max(0, time_remaining)

    def cleanup_expired(self) -> int:
        """Remove expired entries to free memory.

        Call this periodically if you have many unique keys.

        Returns:
            Number of entries cleaned up.
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._entries.items()
                if current_time - entry.first_request_time > self.window_seconds
            ]

            for key in expired_keys:
                del self._entries[key]

            return len(expired_keys)


# Global rate limiter instance for password reset
# Allows 3 requests per email per hour
password_reset_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=3600)
