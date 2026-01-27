# AI Resume Evaluation System Architecture

## Overview

This document describes the architecture for automated **AI resume-to-JD matching evaluation** in Subtribe. The system evaluates job applicant resumes against calibrated job descriptions using AI, with support for thousands of candidates per job.

**Note:** This is specifically for resume-based candidate evaluation. Other AI evaluation types (video interview evaluations, GitHub evaluations, etc.) will have their own architectures.

## Design Principles

1. **Resilience First** - Never lose data, always retry, graceful degradation
2. **Scalability** - Handle thousands of candidates per job
3. **Modularity** - Components can be swapped (e.g., Cloud Tasks → Redis Queue)
4. **Fairness** - Per-company resource allocation based on plan
5. **Observability** - Track progress, timing, and failures

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AI RESUME EVALUATION SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Trigger   │───▶│  Scheduler  │───▶│   Worker    │───▶│   Storage   │  │
│  │   Layer     │    │   Layer     │    │   Layer     │    │   Layer     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│  • Job Calibration   • Batch Creation   • Task Execution  • Results DB     │
│  • New Application   • Task Queueing    • Resume Parse    • Notifications  │
│  • Manual Trigger    • ETA Calculation  • JD Matching     • Progress       │
│                      • Rate Limiting    • Retry Logic                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Trigger Layer

Responsible for initiating AI resume evaluation batches.

**Triggers:**
- Job calibration completion → Batch all pending applications
- New application on calibrated job → Single evaluation task
- Manual trigger via API → Re-evaluate or process specific applications

**Interface:**
```python
class AIResumeEvalTrigger(Protocol):
    async def on_job_calibrated(self, job_id: UUID) -> AIResumeEvalBatch
    async def on_application_created(self, application_id: UUID) -> AIResumeEvalTask | None
    async def trigger_manual(self, job_id: UUID, application_ids: list[UUID]) -> AIResumeEvalBatch
```

### 2. Scheduler Layer

Manages batch creation, task queuing, and rate limiting.

**Responsibilities:**
- Create evaluation batches with accurate ETAs
- Queue tasks with appropriate delays (rate limiting)
- Track company concurrency limits
- Handle task rescheduling

**Interface:**
```python
class AIResumeEvalScheduler(Protocol):
    async def create_batch(self, job_id: UUID, application_ids: list[UUID]) -> AIResumeEvalBatch
    async def queue_task(self, task: AIResumeEvalTask, delay_seconds: int = 0) -> str
    async def reschedule_task(self, task_id: UUID, delay_seconds: int) -> None
    async def can_process(self, company_id: UUID) -> bool
```

### 3. Worker Layer

Executes individual AI resume evaluation tasks.

**Responsibilities:**
- Acquire processing slot (concurrency control)
- Parse resume (PDF → JSON)
- Evaluate against job framework (JD matching)
- Handle errors and retries
- Update task/batch status

**Interface:**
```python
class AIResumeEvalWorker(Protocol):
    async def process_task(self, task_id: UUID) -> AIResumeEvalResult
    async def parse_resume(self, application: Application) -> ParsedResume
    async def evaluate(self, resume: ParsedResume, framework: dict) -> AIResumeEvalResult
```

### 4. Storage Layer

Persists evaluation state and results.

**Responsibilities:**
- Store batch and task state
- Store evaluation results in applications table
- Track progress for dashboard
- Send completion notifications

## Database Schema

### ai_resume_eval_batches

Tracks a batch of AI resume evaluations for a job.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| job_id | UUID | FK to jobs |
| company_id | UUID | FK to companies |
| triggered_by | UUID | FK to users (nullable) |
| status | VARCHAR(50) | pending, processing, completed, failed, cancelled |
| total_count | INT | Total applications in batch |
| queued_count | INT | Tasks queued |
| processing_count | INT | Tasks currently processing |
| completed_count | INT | Successfully completed |
| failed_count | INT | Failed after max retries |
| estimated_seconds | INT | Initial ETA in seconds |
| estimated_completion_at | TIMESTAMPTZ | Calculated completion time |
| started_at | TIMESTAMPTZ | When processing started |
| completed_at | TIMESTAMPTZ | When all tasks finished |
| notification_sent | BOOLEAN | Whether completion email sent |
| rate_limited_until | TIMESTAMPTZ | Rate limit backoff time |
| consecutive_failures | INT | Consecutive failure count |
| created_at | TIMESTAMPTZ | Record creation time |

### ai_resume_eval_tasks

Individual AI resume evaluation task for one application.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| batch_id | UUID | FK to ai_resume_eval_batches |
| application_id | UUID | FK to applications |
| status | VARCHAR(50) | pending, queued, processing, completed, failed, retry_scheduled, skipped |
| attempt_count | INT | Number of attempts |
| max_attempts | INT | Maximum retry attempts (default: 5) |
| last_error | TEXT | Last error message |
| last_error_code | VARCHAR(50) | rate_limit, timeout, api_error, parse_error |
| scheduled_at | TIMESTAMPTZ | When task should execute |
| started_at | TIMESTAMPTZ | When processing started |
| completed_at | TIMESTAMPTZ | When completed |
| next_retry_at | TIMESTAMPTZ | When to retry (if scheduled) |
| cloud_task_name | VARCHAR(500) | GCP Cloud Task reference |
| created_at | TIMESTAMPTZ | Record creation time |
| updated_at | TIMESTAMPTZ | Last update time |

### applications (additional columns)

| Column | Type | Description |
|--------|------|-------------|
| ai_resume_eval_status | VARCHAR(50) | pending, queued, processing, completed, failed, skipped |
| ai_resume_eval_batch_id | UUID | FK to ai_resume_eval_batches (nullable) |
| evaluation_json | JSONB | Full evaluation result |
| evaluation_score | FLOAT | Final score (0-10) |
| evaluation_tier | VARCHAR(50) | strong_match, good_match, moderate_match, weak_match, mismatch |
| evaluated_at | TIMESTAMPTZ | When evaluation completed |

### companies (additional column)

| Column | Type | Description |
|--------|------|-------------|
| max_concurrent_ai_evaluations | INT | Plan-based limit (nullable, uses plan default if null) |

## Flows

### Flow 1: Job Calibration → Batch Evaluation

```
1. Job calibrated (framework saved)
2. Trigger: on_job_calibrated(job_id)
3. Query all applications where job_id = X and ai_resume_eval_status IS NULL
4. Create AIResumeEvalBatch with total_count
5. Calculate ETA based on count and company's max_concurrent
6. Create AIResumeEvalTask for each application
7. Queue Cloud Tasks with staggered delays
8. Return batch with estimated_completion_at
```

### Flow 2: New Application → Single Evaluation

```
1. Application created on calibrated job
2. Trigger: on_application_created(application_id)
3. Check if job.calibrated_at is set
4. If not calibrated → return None (stay pending)
5. If calibrated → create task and queue immediately
6. Evaluation happens, result stored
7. Application auto-ranks with existing candidates
```

### Flow 3: Task Execution

```
1. Cloud Task executes → POST /internal/ai-resume-eval/process/{task_id}
2. Load task from database
3. Check company concurrency limit
4. If at limit → reschedule task (delay 30s)
5. If slot available → acquire slot (status = processing)
6. Parse resume (fetch from GCS, call AI)
7. Evaluate against framework (call AI)
8. Store results in applications table
9. Mark task completed, update batch counts
10. If batch complete → send notification
11. On error → classify, schedule retry or mark failed
```

## Retry Strategy

### Error Classification

| Error Type | Retryable | Base Delay | Example |
|------------|-----------|------------|---------|
| rate_limit | Yes | 60s | 429 Too Many Requests |
| timeout | Yes | 30s | Request timeout |
| api_error | Yes | 120s | 500/502/503/504 |
| parse_error | Yes | 10s | Invalid JSON |
| auth_error | No | - | 401/403 |
| unknown | Yes | 10s | Unclassified |

### Exponential Backoff

```
delay = min(base_delay * 2^attempt + jitter, max_delay)

Example (rate_limit, base=60s):
- Attempt 1: 60s
- Attempt 2: 120s
- Attempt 3: 240s
- Attempt 4: 480s
- Attempt 5: 960s (capped at 1 hour)
```

## Concurrency Control

### Per-Company Limits

| Plan | Max Concurrent | Effective Throughput |
|------|----------------|---------------------|
| Free | 2 | ~8/min |
| Pro | 8 | ~32/min |
| Enterprise | 20 | ~80/min |

### Global Limit

- **Global Max**: 60 concurrent workers
- **Purpose**: Protect against API rate limits (using 50% of Gemini's 1000 RPM)

### Slot Acquisition

```python
# Pseudo-code for slot acquisition
async def acquire_slot(company_id, task_id):
    async with db.transaction():
        # Count active tasks for company
        active = SELECT COUNT(*) FROM ai_resume_eval_tasks t
                 JOIN ai_resume_eval_batches b ON t.batch_id = b.id
                 WHERE b.company_id = company_id
                 AND t.status = 'processing'

        # Get company limit (or use plan default)
        company = SELECT max_concurrent_ai_evaluations, plan
                  FROM companies WHERE id = company_id

        max_concurrent = company.max_concurrent_ai_evaluations
                         or get_limit_for_plan(company.plan)

        if active >= max_concurrent:
            return False  # Reschedule

        # Acquire slot
        UPDATE ai_resume_eval_tasks
        SET status = 'processing', started_at = NOW()
        WHERE id = task_id

        return True
```

## ETA Calculation

```python
def calculate_eta(total_count: int, concurrent_workers: int) -> tuple[int, datetime]:
    """
    Calculate estimated completion time.

    Assumptions:
    - 15 seconds per evaluation (parse + evaluate)
    - 20% buffer for retries/variance
    """
    seconds_per_eval = 15
    buffer = 1.2

    total_seconds = (total_count / concurrent_workers) * seconds_per_eval * buffer
    completion_time = datetime.now(UTC) + timedelta(seconds=total_seconds)

    return int(total_seconds), completion_time
```

## API Endpoints

### Public API

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/jobs/{job_id}/ai-resume-eval/start | POST | Start batch evaluation |
| /api/jobs/{job_id}/ai-resume-eval/status | GET | Get batch status and progress |
| /api/jobs/{job_id}/ai-resume-eval/cancel | POST | Cancel pending batch |

### Internal API (Cloud Tasks)

| Endpoint | Method | Description |
|----------|--------|-------------|
| /internal/ai-resume-eval/process/{task_id} | POST | Process single task |
| /internal/ai-resume-eval/retry-stuck | POST | Cron: reschedule stuck tasks |
| /internal/ai-resume-eval/complete/{batch_id} | POST | Trigger completion notification |

## Directory Structure

```
app/
├── services/
│   └── evaluation/               # AI Resume Evaluation service
│       ├── __init__.py
│       ├── service.py            # Main orchestration service
│       ├── scheduler.py          # Batch creation and task queueing
│       ├── worker.py             # Task execution logic
│       ├── retry.py              # Retry strategy and error classification
│       ├── notifications.py      # Email/notification sending
│       └── config.py             # Configuration and constants
├── models/
│   ├── ai_resume_eval_batch.py   # AIResumeEvalBatch model
│   └── ai_resume_eval_task.py    # AIResumeEvalTask model
├── schemas/
│   └── ai_resume_eval.py         # Request/Response schemas
└── routers/
    └── ai_resume_eval.py         # API endpoints
```

## Configuration

Environment variables (prefix: `AI_RESUME_EVAL_`):

```python
class AIResumeEvalConfig:
    # Timing
    SECONDS_PER_EVALUATION = 15  # AI_RESUME_EVAL_SECONDS_PER_EVAL
    ETA_BUFFER_MULTIPLIER = 1.2  # AI_RESUME_EVAL_ETA_BUFFER

    # Retry
    MAX_ATTEMPTS = 5              # AI_RESUME_EVAL_MAX_RETRY_ATTEMPTS
    BASE_RETRY_DELAY = 10         # AI_RESUME_EVAL_BASE_RETRY_DELAY
    MAX_RETRY_DELAY = 3600        # AI_RESUME_EVAL_MAX_RETRY_DELAY
    RATE_LIMIT_DELAY = 60         # AI_RESUME_EVAL_RATE_LIMIT_DELAY
    TIMEOUT_DELAY = 30            # AI_RESUME_EVAL_TIMEOUT_DELAY
    API_ERROR_DELAY = 120         # AI_RESUME_EVAL_API_ERROR_DELAY

    # Concurrency (per plan)
    FREE_MAX_CONCURRENT = 2       # AI_RESUME_EVAL_CONCURRENT_FREE
    PRO_MAX_CONCURRENT = 8        # AI_RESUME_EVAL_CONCURRENT_PRO
    ENTERPRISE_MAX_CONCURRENT = 20 # AI_RESUME_EVAL_CONCURRENT_ENTERPRISE
    GLOBAL_MAX_CONCURRENT = 60    # AI_RESUME_EVAL_GLOBAL_MAX_CONCURRENT

    # Cloud Tasks
    TASK_QUEUE_NAME = "ai-resume-eval-tasks"  # AI_RESUME_EVAL_TASK_QUEUE_NAME
    TASK_LOCATION = "asia-south1"             # AI_RESUME_EVAL_TASK_LOCATION
    TASK_DEADLINE_SECONDS = 300               # AI_RESUME_EVAL_TASK_DEADLINE

    # Stuck task recovery
    STUCK_TASK_THRESHOLD_MINUTES = 30  # AI_RESUME_EVAL_STUCK_THRESHOLD_MINUTES
```

## Future Scalability Considerations

1. **Horizontal Scaling**: Worker can be deployed as separate service
2. **Queue Migration**: Cloud Tasks → Redis/Celery for higher throughput
3. **Batch Optimization**: Process multiple resumes in single AI call
4. **Caching**: Cache parsed resumes to avoid re-parsing
5. **Priority Queues**: Separate queues for different priorities
6. **Metrics**: Add Prometheus metrics for monitoring
7. **Circuit Breaker**: Pause processing if error rate too high

## Related Systems (Future)

Other AI evaluation systems that will be implemented separately:

- **AI Video Interview Evaluation** - Evaluate video interview responses
- **AI GitHub Evaluation** - Analyze GitHub profiles and contributions
- **AI Portfolio Evaluation** - Analyze portfolio/project links
