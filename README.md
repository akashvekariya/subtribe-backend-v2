# Subtribe Backend

API for Subtribe, a multi-tenant applicant tracking system with AI candidate evaluation. Recruiting teams post jobs, collect applications and get every resume scored against what the role actually needs.

Part of the Subtribe platform: [dashboard](https://github.com/akashvekariya/subtribe-dashboard-v2) for recruiters, [app](https://github.com/akashvekariya/subtribe-app-v2) for candidates, [AI engine](https://github.com/akashvekariya/subtribe-ai-v2).

## Features

- **Multi-tenant by design**: every company's data is isolated, with Postgres row-level security behind the application checks.
- **Jobs and applications**: create and calibrate jobs, public job board and apply flow, status tracking with history.
- **AI resume evaluation**: resumes are parsed and scored in the background through Cloud Tasks, with retries, stuck-job recovery and batch progress.
- **Bulk upload**: drop in a folder of resumes for a job and track the batch.
- **Teams**: invites, roles, email verification, password reset, httpOnly cookie sessions.
- **Email**: templated transactional email through SendGrid, sent asynchronously.
- **Observability**: structured JSON logs with request correlation IDs.

## Stack

FastAPI, async SQLAlchemy, PostgreSQL (Supabase), Alembic, Google Cloud Storage, Cloud Tasks, Cloud Run, SendGrid, pytest, ruff.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # fill in your own values
alembic upgrade head
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

## Tests

```bash
pytest
```

Unit, integration, end-to-end and response-time tests. CI runs lint and tests on every pull request and deploys to staging and production on Cloud Run.

## Layout

```
app/
  routers/    HTTP endpoints (/api/v1, /api/public)
  services/   business logic, evaluation worker, bulk upload
  models/     SQLAlchemy models
  schemas/    request and response models
  email/      providers and templates
  logging/    structured logging and middleware
database/     migrations and row-level security policies
tests/
```
