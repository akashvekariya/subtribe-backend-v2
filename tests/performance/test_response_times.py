"""
Performance tests for API response times.

Measures response times for all endpoints and generates analytics.
Can be run against local or remote servers.

Usage:
- Local: pytest tests/performance/test_response_times.py -v
- Staging: E2E_BASE_URL=https://staging.api.com pytest tests/performance/ -v
"""

import statistics
import time
from collections import defaultdict

import httpx
import pytest

from tests.e2e.config import get_base_url

# Performance thresholds (milliseconds)
THRESHOLDS = {
    "excellent": 100,
    "good": 200,
    "acceptable": 500,
    "slow": 1000,
}


class PerformanceMetrics:
    """Track performance metrics across all tests."""

    def __init__(self):
        self.measurements: dict[str, list[float]] = defaultdict(list)

    def add_measurement(self, endpoint: str, duration_ms: float):
        """Add a measurement for an endpoint."""
        self.measurements[endpoint].append(duration_ms)

    def get_stats(self, endpoint: str) -> dict:
        """Get statistics for an endpoint."""
        if endpoint not in self.measurements:
            return {}

        times = self.measurements[endpoint]
        return {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        }

    def get_performance_rating(self, mean_time: float) -> str:
        """Get performance rating based on mean response time."""
        if mean_time < THRESHOLDS["excellent"]:
            return "⚡ Excellent"
        elif mean_time < THRESHOLDS["good"]:
            return "✅ Good"
        elif mean_time < THRESHOLDS["acceptable"]:
            return "⚠️ Acceptable"
        elif mean_time < THRESHOLDS["slow"]:
            return "🐌 Slow"
        else:
            return "❌ Very Slow"

    def print_summary(self):
        """Print performance summary for all endpoints."""
        print("\n" + "=" * 80)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 80)

        # Sort endpoints by mean response time
        endpoint_stats = []
        for endpoint, _times in self.measurements.items():
            stats = self.get_stats(endpoint)
            endpoint_stats.append((endpoint, stats))

        endpoint_stats.sort(key=lambda x: x[1]["mean"])

        # Print individual endpoint stats
        for endpoint, stats in endpoint_stats:
            rating = self.get_performance_rating(stats["mean"])
            print(f"\n{endpoint}")
            print(f"  Rating: {rating}")
            print(f"  Calls: {stats['count']}")
            print(f"  Mean: {stats['mean']:.2f}ms")
            print(f"  Median: {stats['median']:.2f}ms")
            print(f"  Min: {stats['min']:.2f}ms")
            print(f"  Max: {stats['max']:.2f}ms")
            if stats["stdev"] > 0:
                print(f"  StdDev: {stats['stdev']:.2f}ms")

        # Aggregate stats
        all_times = [t for times in self.measurements.values() for t in times]
        if all_times:
            print("\n" + "-" * 80)
            print("AGGREGATE STATISTICS")
            print("-" * 80)
            print(f"Total API calls: {len(all_times)}")
            print(f"Overall mean: {statistics.mean(all_times):.2f}ms")
            print(f"Overall median: {statistics.median(all_times):.2f}ms")
            print(f"Fastest call: {min(all_times):.2f}ms")
            print(f"Slowest call: {max(all_times):.2f}ms")

            # Performance distribution
            excellent = sum(1 for t in all_times if t < THRESHOLDS["excellent"])
            good = sum(1 for t in all_times if THRESHOLDS["excellent"] <= t < THRESHOLDS["good"])
            acceptable = sum(
                1 for t in all_times if THRESHOLDS["good"] <= t < THRESHOLDS["acceptable"]
            )
            slow = sum(1 for t in all_times if t >= THRESHOLDS["acceptable"])

            print("\nPerformance distribution:")
            print(
                f"  ⚡ Excellent (<{THRESHOLDS['excellent']}ms): {excellent} ({excellent / len(all_times) * 100:.1f}%)"
            )
            print(
                f"  ✅ Good (<{THRESHOLDS['good']}ms): {good} ({good / len(all_times) * 100:.1f}%)"
            )
            print(
                f"  ⚠️ Acceptable (<{THRESHOLDS['acceptable']}ms): {acceptable} ({acceptable / len(all_times) * 100:.1f}%)"
            )
            print(
                f"  🐌 Slow (>={THRESHOLDS['acceptable']}ms): {slow} ({slow / len(all_times) * 100:.1f}%)"
            )

        print("\n" + "=" * 80)


# Global metrics instance
metrics = PerformanceMetrics()


@pytest.fixture(scope="module")
def perf_client():
    """HTTP client for performance tests."""
    base_url = get_base_url()
    client = httpx.Client(base_url=base_url, timeout=30)
    yield client
    client.close()

    # Print summary after all tests
    metrics.print_summary()


@pytest.fixture(scope="module")
def perf_auth_token(perf_client: httpx.Client):
    """Get auth token for performance tests."""
    # Try to register or login
    timestamp = int(time.time())
    test_email = f"perf_test_{timestamp}@example.com"

    response = perf_client.post(
        "/auth/register",
        json={
            "email": test_email,
            "password": "PerfTest123!",
            "first_name": "Performance",
            "last_name": "TestUser",
            "company_code": "FIRSTINVITE",
        },
    )

    if response.status_code == 201:
        return response.json()["access_token"]
    else:
        # Try login if registration fails
        response = perf_client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        if response.status_code == 200:
            return response.json()["access_token"]

        pytest.fail("Could not authenticate for performance tests")


def measure_endpoint(
    client: httpx.Client,
    method: str,
    endpoint: str,
    iterations: int = 5,
    **kwargs,
) -> list[float]:
    """
    Measure endpoint performance over multiple iterations.

    Returns list of response times in milliseconds.
    """
    times = []

    for _ in range(iterations):
        start = time.perf_counter()

        if method == "GET":
            _ = client.get(endpoint, **kwargs)
        elif method == "POST":
            _ = client.post(endpoint, **kwargs)
        elif method == "PATCH":
            _ = client.patch(endpoint, **kwargs)
        elif method == "DELETE":
            _ = client.delete(endpoint, **kwargs)

        duration = (time.perf_counter() - start) * 1000  # Convert to ms
        times.append(duration)

        # Record measurement
        metrics.add_measurement(f"{method} {endpoint}", duration)

        # Small delay between requests
        time.sleep(0.1)

    return times


@pytest.mark.performance
class TestHealthEndpoint:
    """Test health check endpoint performance."""

    def test_health_check_performance(self, perf_client: httpx.Client):
        """Measure /health endpoint (should be fastest)."""
        times = measure_endpoint(perf_client, "GET", "/health", iterations=10)

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["excellent"], f"Health check too slow: {mean_time:.2f}ms"
        print(f"\n/health: {mean_time:.2f}ms (avg of {len(times)} calls)")


@pytest.mark.performance
class TestAuthEndpoints:
    """Test authentication endpoint performance."""

    def test_auth_me_performance(self, perf_client: httpx.Client, perf_auth_token: str):
        """Measure GET /auth/me performance."""
        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(perf_client, "GET", "/auth/me", headers=headers, iterations=10)

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"/auth/me too slow: {mean_time:.2f}ms"
        print(f"\nGET /auth/me: {mean_time:.2f}ms")

    def test_login_performance(self, perf_client: httpx.Client):
        """Measure POST /auth/login performance."""
        # Note: Login involves password hashing, will be slower
        times = measure_endpoint(
            perf_client,
            "POST",
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
            iterations=5,
        )

        mean_time = statistics.mean(times)
        # Login can be slower due to bcrypt
        assert mean_time < THRESHOLDS["acceptable"], f"Login too slow: {mean_time:.2f}ms"
        print(f"\nPOST /auth/login: {mean_time:.2f}ms")


@pytest.mark.performance
class TestJobEndpoints:
    """Test job endpoint performance."""

    @pytest.fixture(scope="class")
    def test_job_id(self, perf_client: httpx.Client, perf_auth_token: str):
        """Create a test job for performance tests."""
        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        response = perf_client.post(
            "/jobs",
            headers=headers,
            json={
                "title": "Performance Test Job",
                "description": "Test job - testing skills required",
                "department": "Engineering",
                "position_type": "full_time",
                "location_type": "hybrid",
                "location_city": "Mumbai",
                "location_country": "India",
            },
        )
        if response.status_code == 201:
            job = response.json()
            return job["id"], job["slug"]
        return None, None

    def test_list_jobs_performance(self, perf_client: httpx.Client, perf_auth_token: str):
        """Measure GET /jobs performance."""
        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(perf_client, "GET", "/jobs", headers=headers, iterations=10)

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"List jobs too slow: {mean_time:.2f}ms"
        print(f"\nGET /jobs: {mean_time:.2f}ms")

    def test_get_job_performance(
        self, perf_client: httpx.Client, perf_auth_token: str, test_job_id
    ):
        """Measure GET /jobs/{id} performance."""
        job_id, _ = test_job_id
        if not job_id:
            pytest.skip("No test job available")

        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(
            perf_client, "GET", f"/jobs/{job_id}", headers=headers, iterations=10
        )

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"Get job too slow: {mean_time:.2f}ms"
        print(f"\nGET /jobs/{{id}}: {mean_time:.2f}ms")

    def test_public_job_page_performance(self, perf_client: httpx.Client, test_job_id):
        """Measure GET /public/jobs/{slug} performance."""
        _, slug = test_job_id
        if not slug:
            pytest.skip("No test job available")

        # Publish job first
        times = measure_endpoint(perf_client, "GET", f"/public/jobs/{slug}", iterations=10)

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"Public job page too slow: {mean_time:.2f}ms"
        print(f"\nGET /public/jobs/{{slug}}: {mean_time:.2f}ms")


@pytest.mark.performance
class TestApplicationEndpoints:
    """Test application endpoint performance."""

    @pytest.fixture(scope="class")
    def test_application_id(self, perf_client: httpx.Client, perf_auth_token: str):
        """Create a test application for performance tests."""
        # First create and publish a job
        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        job_response = perf_client.post(
            "/jobs",
            headers=headers,
            json={
                "title": "Perf Test App Job",
                "description": "Test job for performance testing",
                "department": "Engineering",
                "position_type": "full_time",
                "location_type": "hybrid",
                "location_city": "Mumbai",
                "location_country": "India",
            },
        )

        if job_response.status_code != 201:
            return None

        job = job_response.json()
        slug = job["slug"]

        # Publish job
        perf_client.patch(
            f"/jobs/{job['id']}",
            headers=headers,
            json={"status": "active"},
        )

        # Submit application
        pdf_content = b"%PDF-1.4\n%%EOF"
        timestamp = int(time.time())

        app_response = perf_client.post(
            f"/public/jobs/{slug}/apply",
            data={
                "first_name": "Perf",
                "last_name": "Candidate",
                "email": f"perf_app_{timestamp}@example.com",
                "phone": "+919876543210",
                "current_ctc": "800000",
                "expected_ctc": "1200000",
                "notice_period_days": "30",
            },
            files={"resume": ("resume.pdf", pdf_content, "application/pdf")},
        )

        if app_response.status_code == 201:
            return app_response.json()["id"], job["id"]
        return None, None

    def test_list_applications_performance(
        self, perf_client: httpx.Client, perf_auth_token: str, test_application_id
    ):
        """Measure GET /jobs/{job_id}/applications performance."""
        app_id, job_id = test_application_id
        if not job_id:
            pytest.skip("No test application available")

        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(
            perf_client,
            "GET",
            f"/jobs/{job_id}/applications",
            headers=headers,
            iterations=10,
        )

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"List applications too slow: {mean_time:.2f}ms"
        print(f"\nGET /jobs/{{job_id}}/applications: {mean_time:.2f}ms")

    def test_get_application_performance(
        self, perf_client: httpx.Client, perf_auth_token: str, test_application_id
    ):
        """Measure GET /applications/{id} performance."""
        app_id, _ = test_application_id
        if not app_id:
            pytest.skip("No test application available")

        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(
            perf_client,
            "GET",
            f"/applications/{app_id}",
            headers=headers,
            iterations=10,
        )

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"Get application too slow: {mean_time:.2f}ms"
        print(f"\nGET /applications/{{id}}: {mean_time:.2f}ms")

    def test_get_application_history_performance(
        self, perf_client: httpx.Client, perf_auth_token: str, test_application_id
    ):
        """Measure GET /applications/{id}/history performance."""
        app_id, _ = test_application_id
        if not app_id:
            pytest.skip("No test application available")

        headers = {"Authorization": f"Bearer {perf_auth_token}"}
        times = measure_endpoint(
            perf_client,
            "GET",
            f"/applications/{app_id}/history",
            headers=headers,
            iterations=10,
        )

        mean_time = statistics.mean(times)
        assert mean_time < THRESHOLDS["good"], f"Get history too slow: {mean_time:.2f}ms"
        print(f"\nGET /applications/{{id}}/history: {mean_time:.2f}ms")
