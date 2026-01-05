"""
AI Resume Evaluation System Configuration.

All settings are configurable via environment variables for easy tuning
without code changes. This allows scaling up as API limits increase.

This is specifically for AI resume-to-JD matching evaluation. Other AI evaluation
types (video interview evaluations, GitHub evaluations, etc.) will have their own configs.

Environment Variables:
    AI_RESUME_EVAL_CONCURRENT_FREE: Max concurrent evaluations for free tier (default: 2)
    AI_RESUME_EVAL_CONCURRENT_PRO: Max concurrent evaluations for pro tier (default: 8)
    AI_RESUME_EVAL_CONCURRENT_ENTERPRISE: Max concurrent evaluations for enterprise (default: 20)
    AI_RESUME_EVAL_GLOBAL_MAX_CONCURRENT: Global max across all companies (default: 60)
    AI_RESUME_EVAL_SECONDS_PER_EVAL: Estimated seconds per evaluation (default: 15)
    AI_RESUME_EVAL_MAX_RETRY_ATTEMPTS: Max retry attempts per task (default: 5)
    AI_RESUME_EVAL_RATE_LIMIT_DELAY: Delay after rate limit error in seconds (default: 60)
    AI_RESUME_EVAL_TIMEOUT_DELAY: Delay after timeout error in seconds (default: 30)
    AI_RESUME_EVAL_API_ERROR_DELAY: Delay after API error in seconds (default: 120)
    AI_RESUME_EVAL_BASE_RETRY_DELAY: Base delay for exponential backoff (default: 10)
    AI_RESUME_EVAL_MAX_RETRY_DELAY: Maximum retry delay in seconds (default: 3600)

Scaling Notes:
    - Current config assumes Gemini paid tier (~1000 RPM)
    - Using 50% of capacity = 500 RPM for evaluations
    - Each evaluation = 2 API calls (parse + evaluate)
    - At 15 sec/eval, each worker does ~8 API calls/min
    - Global max 60 workers = ~480 API calls/min (within 500 RPM budget)

To increase capacity:
    1. Verify API limits with provider
    2. Increase AI_RESUME_EVAL_GLOBAL_MAX_CONCURRENT
    3. Increase per-plan limits proportionally
    4. Monitor error rates and adjust
"""

import os
from dataclasses import dataclass
from enum import Enum


class CompanyPlan(str, Enum):
    """Company subscription plans."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class RetryConfig:
    """
    Retry configuration for AI resume evaluation tasks.

    Uses exponential backoff with error-specific base delays.
    Formula: delay = min(base_delay * 2^attempt + jitter, max_delay)
    """

    max_attempts: int = int(os.getenv("AI_RESUME_EVAL_MAX_RETRY_ATTEMPTS", "5"))

    # Base delays by error type (seconds)
    rate_limit_delay: int = int(os.getenv("AI_RESUME_EVAL_RATE_LIMIT_DELAY", "60"))
    timeout_delay: int = int(os.getenv("AI_RESUME_EVAL_TIMEOUT_DELAY", "30"))
    api_error_delay: int = int(os.getenv("AI_RESUME_EVAL_API_ERROR_DELAY", "120"))
    parse_error_delay: int = int(os.getenv("AI_RESUME_EVAL_PARSE_ERROR_DELAY", "10"))
    base_retry_delay: int = int(os.getenv("AI_RESUME_EVAL_BASE_RETRY_DELAY", "10"))

    # Maximum delay cap (1 hour)
    max_retry_delay: int = int(os.getenv("AI_RESUME_EVAL_MAX_RETRY_DELAY", "3600"))

    # Jitter percentage (±20%)
    jitter_percent: float = 0.2


@dataclass(frozen=True)
class ConcurrencyConfig:
    """
    Concurrency limits for AI resume evaluation processing.

    Limits are per-company and based on subscription plan.
    Global limit ensures we don't exceed API rate limits.
    """

    # Per-plan concurrent evaluation limits
    free_max_concurrent: int = int(os.getenv("AI_RESUME_EVAL_CONCURRENT_FREE", "2"))
    pro_max_concurrent: int = int(os.getenv("AI_RESUME_EVAL_CONCURRENT_PRO", "8"))
    enterprise_max_concurrent: int = int(os.getenv("AI_RESUME_EVAL_CONCURRENT_ENTERPRISE", "20"))

    # Global limit across all companies (API rate limit protection)
    global_max_concurrent: int = int(os.getenv("AI_RESUME_EVAL_GLOBAL_MAX_CONCURRENT", "60"))

    # Default for companies without explicit plan
    default_max_concurrent: int = int(os.getenv("AI_RESUME_EVAL_CONCURRENT_DEFAULT", "2"))

    def get_limit_for_plan(self, plan: str | CompanyPlan) -> int:
        """Get concurrent evaluation limit for a plan."""
        if isinstance(plan, str):
            plan = plan.lower()

        limits = {
            "free": self.free_max_concurrent,
            CompanyPlan.FREE: self.free_max_concurrent,
            "pro": self.pro_max_concurrent,
            CompanyPlan.PRO: self.pro_max_concurrent,
            "enterprise": self.enterprise_max_concurrent,
            CompanyPlan.ENTERPRISE: self.enterprise_max_concurrent,
        }
        return limits.get(plan, self.default_max_concurrent)


@dataclass(frozen=True)
class TimingConfig:
    """
    Timing configuration for ETA calculations and scheduling.
    """

    # Average time per evaluation (parse + evaluate)
    seconds_per_evaluation: int = int(os.getenv("AI_RESUME_EVAL_SECONDS_PER_EVAL", "15"))

    # Buffer multiplier for ETA (accounts for retries, variance)
    eta_buffer_multiplier: float = float(os.getenv("AI_RESUME_EVAL_ETA_BUFFER", "1.2"))

    # Delay when slot not available (seconds)
    slot_wait_delay: int = int(os.getenv("AI_RESUME_EVAL_SLOT_WAIT_DELAY", "30"))

    # Threshold for considering a task "stuck" (minutes)
    stuck_task_threshold_minutes: int = int(
        os.getenv("AI_RESUME_EVAL_STUCK_THRESHOLD_MINUTES", "30")
    )


@dataclass(frozen=True)
class CloudTasksConfig:
    """
    Google Cloud Tasks configuration for AI resume evaluation.
    """

    # Queue name for AI resume evaluation tasks
    queue_name: str = os.getenv("AI_RESUME_EVAL_TASK_QUEUE_NAME", "ai-resume-eval-tasks")

    # GCP location/region
    location: str = os.getenv("AI_RESUME_EVAL_TASK_LOCATION", "asia-south1")

    # Task execution deadline (seconds)
    task_deadline_seconds: int = int(os.getenv("AI_RESUME_EVAL_TASK_DEADLINE", "300"))

    # Service URL for task callbacks (set in production)
    service_url: str = os.getenv("AI_RESUME_EVAL_SERVICE_URL", "http://localhost:8000")


@dataclass(frozen=True)
class AIResumeEvalConfig:
    """
    Main configuration container for the AI resume evaluation system.

    This handles resume-to-JD matching using AI. Other evaluation types
    (video interview, GitHub, etc.) will have separate configurations.

    Usage:
        from app.services.evaluation.config import config

        # Get concurrency limit
        limit = config.concurrency.get_limit_for_plan("enterprise")

        # Get retry delay
        delay = config.retry.rate_limit_delay
    """

    retry: RetryConfig = RetryConfig()
    concurrency: ConcurrencyConfig = ConcurrencyConfig()
    timing: TimingConfig = TimingConfig()
    cloud_tasks: CloudTasksConfig = CloudTasksConfig()

    def __post_init__(self) -> None:
        """Validate configuration on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values."""
        # Ensure per-plan limits don't exceed global
        if self.concurrency.enterprise_max_concurrent > self.concurrency.global_max_concurrent:
            import logging

            logging.warning(
                f"Enterprise concurrent limit ({self.concurrency.enterprise_max_concurrent}) "
                f"exceeds global limit ({self.concurrency.global_max_concurrent}). "
                "Enterprise limit will be effectively capped at global limit."
            )


# Singleton configuration instance
config = AIResumeEvalConfig()


# Convenience exports
RETRY_CONFIG = config.retry
CONCURRENCY_CONFIG = config.concurrency
TIMING_CONFIG = config.timing
CLOUD_TASKS_CONFIG = config.cloud_tasks


def get_throughput_estimate(concurrent_workers: int) -> dict:
    """
    Calculate estimated throughput for given number of workers.

    Args:
        concurrent_workers: Number of concurrent evaluation workers

    Returns:
        Dict with throughput metrics
    """
    evals_per_minute = (60 / config.timing.seconds_per_evaluation) * concurrent_workers
    api_calls_per_minute = evals_per_minute * 2  # parse + evaluate

    return {
        "concurrent_workers": concurrent_workers,
        "evaluations_per_minute": round(evals_per_minute, 1),
        "api_calls_per_minute": round(api_calls_per_minute, 1),
        "time_for_100_apps_minutes": round(100 / evals_per_minute, 1),
        "time_for_1000_apps_minutes": round(1000 / evals_per_minute, 1),
        "time_for_10000_apps_hours": round(10000 / evals_per_minute / 60, 1),
    }


def print_config_summary() -> None:
    """Print configuration summary for debugging."""
    print("\n" + "=" * 60)
    print("AI RESUME EVALUATION SYSTEM CONFIGURATION")
    print("=" * 60)

    print("\nConcurrency Limits:")
    print(f"  Free tier:       {config.concurrency.free_max_concurrent} workers")
    print(f"  Pro tier:        {config.concurrency.pro_max_concurrent} workers")
    print(f"  Enterprise tier: {config.concurrency.enterprise_max_concurrent} workers")
    print(f"  Global max:      {config.concurrency.global_max_concurrent} workers")

    print("\nThroughput Estimates (Enterprise):")
    stats = get_throughput_estimate(config.concurrency.enterprise_max_concurrent)
    print(f"  Evaluations/min: {stats['evaluations_per_minute']}")
    print(f"  API calls/min:   {stats['api_calls_per_minute']}")
    print(f"  1000 apps:       {stats['time_for_1000_apps_minutes']} minutes")
    print(f"  10000 apps:      {stats['time_for_10000_apps_hours']} hours")

    print("\nRetry Configuration:")
    print(f"  Max attempts:    {config.retry.max_attempts}")
    print(f"  Rate limit delay: {config.retry.rate_limit_delay}s")
    print(f"  Max retry delay: {config.retry.max_retry_delay}s")

    print("\nCloud Tasks:")
    print(f"  Queue:    {config.cloud_tasks.queue_name}")
    print(f"  Location: {config.cloud_tasks.location}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Run this file directly to see current configuration
    print_config_summary()
