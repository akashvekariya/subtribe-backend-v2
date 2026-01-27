# Application Submission & AI Evaluation Flow - V1

> **Status**: Design Document
> **Version**: 1.0
> **Created**: 2026-01-15
> **Purpose**: Define the new application submission and AI evaluation pipeline

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Architecture](#architecture)
4. [New Endpoints](#new-endpoints)
5. [Database Changes](#database-changes)
6. [Detailed Flow](#detailed-flow)
7. [AI Package Integration](#ai-package-integration)
8. [Error Handling](#error-handling)
9. [Implementation Checklist](#implementation-checklist)

---

## Overview

### What This Document Covers

This document defines the **new** application submission and AI evaluation pipeline. It introduces:

- New endpoint(s) under `/api/v1/` prefix
- Updated worker logic using `subtribe_ai.parse_resume()`
- File hash generation for duplicate detection
- Clean separation of concerns between backend and AI package

### What This Document Does NOT Cover

- Existing endpoints (remain untouched)
- Framework creation flow (already working)
- Frontend changes

### Migration Strategy

| Aspect | Approach |
|--------|----------|
| Old endpoints | Keep running, no changes |
| New endpoints | `/api/v1/` prefix |
| Code duplication | Acceptable during transition |
| Cleanup | After new flow is tested |

---

## Design Principles

### 1. Fast Response to Candidate

The candidate should receive a response within **500ms**. All AI processing happens asynchronously after the response is sent.

### 2. Transactional Safety

Application must be **saved to database** before any AI processing begins. If AI fails, the application is still recorded.

### 3. Separation of Concerns

| Layer | Responsibility |
|-------|----------------|
| **Backend** | Validation, storage (GCS), database, task orchestration |
| **AI Package** | PDF parsing, resume extraction, evaluation logic |

Backend passes PDF bytes to AI package. AI package returns structured data. Backend stores results.

### 4. Retry-Friendly

Every step can be retried independently:
- PDF stored in GCS (can re-download)
- Task status tracked in database
- Checkpoints after each AI step

### 5. Single AI Call for Parsing

Use `subtribe_ai.parse_resume(pdf_bytes)` which internally handles:
- Link extraction (PyMuPDF)
- PDF to Markdown (Gemini)
- Markdown to JSON (BAML)
- Post-processing

Backend does NOT call BAML directly.

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                           PHASE 1: SUBMISSION                               │
│                        (Synchronous - Fast Response)                        │
│                                                                             │
│    Candidate ──► Validate ──► Hash ──► Upload GCS ──► Save DB ──► Response  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Trigger async task
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          PHASE 2: AI PROCESSING                             │
│                         (Asynchronous - Background)                         │
│                                                                             │
│    Download PDF ──► parse_resume() ──► Save ──► evaluate_candidate() ──► Save│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Router    │  │   Storage   │  │  Database   │  │   Worker    │        │
│  │  (FastAPI)  │  │   (GCS)     │  │ (Postgres)  │  │(Cloud Tasks)│        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         │   Validate     │   Upload PDF   │   Save app     │   Process     │
│         │   + Hash       │   Download PDF │   Save results │   tasks       │
│         │                │                │                │               │
└─────────┴────────────────┴────────────────┴────────────────┴───────────────┘
                                        │
                                        │ Function calls only
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SUBTRIBE-AI PACKAGE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐       ┌─────────────────────┐                     │
│  │   parse_resume()    │       │ evaluate_candidate()│                     │
│  │                     │       │                     │                     │
│  │  PDF bytes ──►      │       │  parsed_resume ──►  │                     │
│  │  ParsedResume dict  │       │  EvaluationResult   │                     │
│  │                     │       │                     │                     │
│  │  (handles all       │       │  (handles BAML +    │                     │
│  │   internal steps)   │       │   post-processing)  │                     │
│  └─────────────────────┘       └─────────────────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## New Endpoints

### Summary

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/jobs/{job_slug}/apply` | Submit application | Public |

**Note**: Only ONE new endpoint is needed. The Cloud Tasks callback endpoint (`/ai-resume-eval/internal/process/{task_id}`) already exists and will be reused with updated worker logic.

---

### POST `/api/v1/jobs/{job_slug}/apply`

Submit a job application with resume.

#### Request

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `first_name` | string | Yes | Candidate first name (1-100 chars) |
| `last_name` | string | Yes | Candidate last name (1-100 chars) |
| `email` | string | Yes | Candidate email |
| `phone` | string | No | Phone number |
| `linkedin_url` | string | No | LinkedIn profile URL |
| `github_url` | string | No | GitHub profile URL |
| `portfolio_url` | string | No | Portfolio URL |
| `cover_letter` | string | No | Cover letter (max 5000 chars) |
| `current_ctc` | integer | No | Current CTC |
| `expected_ctc` | integer | No | Expected CTC |
| `notice_period_days` | integer | No | Notice period in days |
| `screening_answers` | string | No | JSON string of screening answers |
| `resume` | file | Yes | PDF file (max 5MB) |

#### Response

**Success (201 Created)**:

```json
{
  "id": "uuid",
  "message": "Application submitted successfully",
  "status": "pending_evaluation"
}
```

**Errors**:

| Status | Code | Description |
|--------|------|-------------|
| 400 | `invalid_file_type` | Only PDF files allowed |
| 400 | `file_too_large` | File exceeds 5MB limit |
| 400 | `invalid_json` | Invalid screening_answers format |
| 404 | `job_not_found` | Job not found or not active |
| 409 | `duplicate_application` | Already applied with this email |

#### Example

```bash
curl -X POST "https://api.example.com/api/v1/jobs/senior-engineer/apply" \
  -F "first_name=John" \
  -F "last_name=Doe" \
  -F "email=john@example.com" \
  -F "resume=@resume.pdf"
```

---

## Database Changes

### New Column: `resume_file_hash`

Add to `applications` table:

```sql
ALTER TABLE applications
ADD COLUMN resume_file_hash VARCHAR(64) NULL;

-- Index for duplicate detection queries
CREATE INDEX idx_applications_resume_hash ON applications(resume_file_hash);
```

#### Migration File

```python
"""add_resume_file_hash_to_applications

Revision ID: <auto>
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        'applications',
        sa.Column('resume_file_hash', sa.String(64), nullable=True)
    )
    op.create_index(
        'idx_applications_resume_hash',
        'applications',
        ['resume_file_hash']
    )

def downgrade() -> None:
    op.drop_index('idx_applications_resume_hash', table_name='applications')
    op.drop_column('applications', 'resume_file_hash')
```

#### Model Update

```python
# In app/models/application.py

class Application(Base):
    # ... existing fields ...

    # Resume file hash for duplicate detection
    resume_file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 hash of PDF bytes
```

---

## Detailed Flow

### Phase 1: Application Submission (Synchronous)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  POST /api/v1/jobs/{job_slug}/apply                                         │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: VALIDATE JOB
────────────────────
    │
    ├── Query: SELECT * FROM jobs WHERE slug = {job_slug}
    │
    ├── Check: job exists?
    │   └── NO  → Return 404 "Job not found"
    │
    ├── Check: job.status == "active"?
    │   └── NO  → Return 404 "Job not accepting applications"
    │
    └── PASS → Continue

Step 2: VALIDATE FILE
─────────────────────
    │
    ├── Check: content_type == "application/pdf"?
    │   └── NO  → Return 400 "Only PDF files allowed"
    │
    ├── Check: file_size <= 5MB?
    │   └── NO  → Return 400 "File too large"
    │
    └── PASS → Continue

Step 3: CHECK DUPLICATE
───────────────────────
    │
    ├── Query: SELECT * FROM applications
    │          WHERE job_id = {job.id} AND email = {email}
    │
    ├── Check: exists?
    │   └── YES → Return 409 "Already applied"
    │
    └── PASS → Continue

Step 4: GENERATE FILE HASH
──────────────────────────
    │
    ├── Read PDF bytes into memory
    │
    ├── Compute: SHA-256 hash of bytes
    │   └── hash = hashlib.sha256(pdf_bytes).hexdigest()
    │
    └── Store hash for later

Step 5: UPLOAD TO GCS
─────────────────────
    │
    ├── Generate path: gs://bucket/{company_id}/{job_id}/{app_id}_{timestamp}_{name}.pdf
    │
    ├── Upload: storage_service.upload_resume(...)
    │
    ├── On failure:
    │   └── Return 503 "Upload failed, please retry"
    │
    └── Store resume_url

Step 6: SAVE TO DATABASE
────────────────────────
    │
    ├── Create Application record:
    │   {
    │     job_id, company_id,
    │     first_name, last_name, email, phone,
    │     linkedin_url, github_url, portfolio_url,
    │     cover_letter, current_ctc, expected_ctc, notice_period_days,
    │     screening_answers,
    │     resume_url,              ← GCS path
    │     resume_filename,         ← Original filename
    │     resume_file_hash,        ← SHA-256 hash (NEW)
    │     status: "applied",
    │     ai_resume_eval_status: "pending"
    │   }
    │
    ├── Create ApplicationStatusHistory record:
    │   {
    │     application_id,
    │     from_status: null,
    │     to_status: "applied",
    │     notes: "Application submitted"
    │   }
    │
    ├── COMMIT transaction
    │
    └── On failure: ROLLBACK, return 500

Step 7: RETURN RESPONSE
───────────────────────
    │
    ├── Return 201:
    │   {
    │     "id": "{application_id}",
    │     "message": "Application submitted successfully",
    │     "status": "pending_evaluation"
    │   }
    │
    └── Response sent to candidate (< 500ms target)

Step 8: TRIGGER AI PROCESSING (Fire-and-Forget)
───────────────────────────────────────────────
    │
    ├── Check: job.evaluation_framework exists?
    │   └── NO  → Skip AI processing (job not calibrated)
    │
    ├── Create AIResumeEvalBatch record
    │
    ├── Create AIResumeEvalTask record
    │
    ├── Queue to Cloud Tasks
    │
    └── On failure: Log warning, don't fail the response
        (Application is saved, AI can be triggered manually later)
```

---

### Phase 2: AI Processing (Asynchronous)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cloud Tasks callback: POST /ai-resume-eval/internal/process/{task_id}      │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: LOAD CONTEXT
────────────────────
    │
    ├── Load AIResumeEvalTask from database
    │
    ├── Check: task.status is terminal?
    │   └── YES → Return early (already processed)
    │
    ├── Load Application record
    │
    ├── Load Job record (for evaluation_framework)
    │
    ├── Check: job.evaluation_framework exists?
    │   └── NO  → Mark task failed, return
    │
    └── Mark task as "processing"

Step 2: DOWNLOAD PDF
────────────────────
    │
    ├── Check: application.resume_parsed_json exists?
    │   └── YES → Skip to Step 4 (already parsed)
    │
    ├── Download from GCS:
    │   pdf_bytes = storage_service.download_file(application.resume_url)
    │
    └── On failure: Retry with backoff

Step 3: PARSE RESUME (PDF → Markdown + JSON)
────────────────────────────────────────────
    │
    ├── Call subtribe_ai:
    │
    │   from subtribe_ai import parse_resume
    │
    │   parsed_result = parse_resume(pdf_bytes)
    │
    │   # Returns:
    │   # {
    │   #   "markdown": "...",           ← Gemini-extracted text
    │   #   "personal_info": {...},
    │   #   "experience": [...],
    │   #   "education": [...],
    │   #   "projects": [...],
    │   #   "skills": {...},
    │   #   "computed": {...},           ← Post-processed metrics
    │   #   "timing": {...}
    │   # }
    │
    ├── On failure: Retry with backoff (rate limits, etc.)
    │
    └── Continue to save

Step 4: SAVE PARSING RESULTS (Checkpoint)
─────────────────────────────────────────
    │
    ├── Update Application:
    │   {
    │     resume_parsed_md: parsed_result["markdown"],
    │     resume_parsed_json: parsed_result
    │   }
    │
    ├── COMMIT to database
    │
    └── Log: "Parsing complete for application {id}"

Step 5: EVALUATE CANDIDATE (JSON → Evaluation)
──────────────────────────────────────────────
    │
    ├── Call subtribe_ai:
    │
    │   from subtribe_ai import evaluate_candidate
    │
    │   evaluation = evaluate_candidate(
    │       parsed_resume=application.resume_parsed_json,
    │       framework=job.evaluation_framework
    │   )
    │
    │   # Returns:
    │   # {
    │   #   "scores": {
    │   #     "final_score": 7.5,
    │   #     "tier": "good_match",
    │   #     "dimension_scores": {...},
    │   #     "verification_confidence": "high"
    │   #   },
    │   #   "manipulation_check": {...},
    │   #   "red_flags": {...},
    │   #   "blockers": [...],
    │   #   "can_proceed": true,
    │   #   "analysis": {...},
    │   #   "evaluation": {...},
    │   #   "warnings": [...],
    │   #   "timing": {...}
    │   # }
    │
    ├── On failure: Retry with backoff
    │
    └── Continue to save

Step 6: SAVE EVALUATION RESULTS (Final)
───────────────────────────────────────
    │
    ├── Extract key fields:
    │   final_score = evaluation["scores"]["final_score"]
    │   tier = evaluation["scores"]["tier"]
    │   is_blocked = len(evaluation["blockers"]) > 0
    │   is_flagged = evaluation["manipulation_check"].get("detected", False)
    │
    ├── Update Application:
    │   {
    │     evaluation_json: evaluation,
    │     evaluation_score: final_score,
    │     evaluation_tier: tier,
    │     is_dealbreaker: is_blocked,
    │     is_flagged: is_flagged,
    │     evaluated_at: now(),
    │     ai_resume_eval_status: "completed"
    │   }
    │
    ├── Mark AIResumeEvalTask as "completed"
    │
    ├── COMMIT to database
    │
    └── Log: "Evaluation complete: score={score}, tier={tier}"
```

---

## AI Package Integration

### Functions Used

| Function | Input | Output | When Called |
|----------|-------|--------|-------------|
| `parse_resume(pdf_bytes)` | Raw PDF bytes | `ParsedResume` dict | Phase 2, Step 3 |
| `evaluate_candidate(parsed_resume, framework)` | Parsed resume + framework | `EvaluationResult` dict | Phase 2, Step 5 |

### What Backend Does NOT Do

- Does NOT call BAML directly
- Does NOT extract links manually
- Does NOT do post-processing of AI results
- Does NOT convert PDF to markdown manually

### What AI Package Handles Internally

```
parse_resume(pdf_bytes):
    ├── Write bytes to temp file
    ├── Extract links using PyMuPDF
    ├── Convert PDF to base64
    ├── Call b.ExtractResumeToMarkdown() ← BAML
    ├── Call b.ParseResume() ← BAML
    ├── Run post-processing
    └── Return combined result

evaluate_candidate(parsed_resume, framework):
    ├── Serialize inputs to JSON
    ├── Call b.EvaluateCandidate() ← BAML
    ├── Run scoring pipeline
    ├── Run red flag detection
    ├── Sanitize for frontend
    └── Return evaluation result
```

---

## Error Handling

### Phase 1 Errors (Submission)

| Error | Response | Recovery |
|-------|----------|----------|
| Invalid file type | 400 | User fixes and resubmits |
| File too large | 400 | User compresses and resubmits |
| Duplicate application | 409 | User informed, no action needed |
| GCS upload failed | 503 | User retries |
| Database error | 500 | User retries |

### Phase 2 Errors (AI Processing)

| Error | Action | Retry? |
|-------|--------|--------|
| PDF download failed | Mark for retry | Yes, with backoff |
| parse_resume() failed | Mark for retry | Yes, with backoff |
| evaluate_candidate() failed | Mark for retry | Yes, with backoff |
| Rate limit hit | Schedule retry | Yes, with delay |
| Max retries exceeded | Mark as failed | No, manual intervention |

### Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay_seconds": 60,
    "backoff_multiplier": 2,
    # Retry 1: 60s, Retry 2: 120s, Retry 3: 240s
}
```

---

## Implementation Checklist

### Prerequisites

- [ ] Confirm subtribe_ai package is installed and working
- [ ] Confirm `parse_resume()` returns expected structure
- [ ] Confirm `evaluate_candidate()` returns expected structure

### Database

- [ ] Create migration for `resume_file_hash` column
- [ ] Update `Application` model with new column
- [ ] Run migration on dev environment

### New Endpoint

- [ ] Create `/api/v1/` router structure
- [ ] Implement `POST /api/v1/jobs/{job_slug}/apply`
- [ ] Add file hash generation (SHA-256)
- [ ] Add request validation
- [ ] Add response schema
- [ ] Add to FastAPI app router

### Worker Update

- [ ] Update worker to use `parse_resume(pdf_bytes)`
- [ ] Remove direct BAML calls
- [ ] Update result extraction logic
- [ ] Test with sample PDFs

### Testing

- [ ] Test endpoint with valid PDF
- [ ] Test endpoint with invalid file type
- [ ] Test endpoint with oversized file
- [ ] Test duplicate application handling
- [ ] Test AI processing flow end-to-end
- [ ] Test retry mechanism

### Cleanup (After Testing)

- [ ] Remove old endpoint (or deprecate)
- [ ] Remove duplicated code
- [ ] Update documentation

---

## File Structure

```
app/
├── routers/
│   ├── v1/                          ← NEW
│   │   ├── __init__.py
│   │   └── applications.py          ← New endpoint
│   ├── applications.py              ← Keep existing
│   └── ...
├── services/
│   └── evaluation/
│       └── worker.py                ← Update this
├── models/
│   └── application.py               ← Add resume_file_hash
└── main.py                          ← Register v1 router
```

---

## Summary

| What | Before | After |
|------|--------|-------|
| **PDF Parsing** | Direct BAML calls in worker | `parse_resume(pdf_bytes)` |
| **Checkpoints** | Save after each BAML call | Save after `parse_resume()` |
| **File Hash** | Not stored | SHA-256 stored |
| **Endpoint** | `/applications/jobs/{slug}/apply` | `/api/v1/jobs/{slug}/apply` |
| **Concerns** | Mixed in worker | Separated (backend vs AI package) |

This design provides:
1. **Fast response** to candidates
2. **Reliable** async processing
3. **Clean separation** of concerns
4. **Retry-friendly** architecture
5. **Future-proof** duplicate detection
