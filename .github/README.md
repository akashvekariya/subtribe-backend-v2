# CI/CD Pipeline Setup & Usage

> **Status**: ✅ Production Deployed & Tested (2025-10-12)  
> **Workflow**: `.github/workflows/main.yml`  
> **Cloud Run**: Live and operational

## 📋 Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [GitHub Setup](#github-setup)
4. [GCP Setup](#gcp-setup)
5. [First Deployment (v1.0.0)](#first-deployment-v100)
6. [Daily Workflow](#daily-workflow)
7. [Troubleshooting](#troubleshooting)

---

## Overview

**Single Workflow, Two Jobs:**
- `.github/workflows/main.yml`
  - **Job 1: `lint-test`** - Runs on all pushes/PRs (linting, formatting, tests)
  - **Job 2: `deploy`** - Runs ONLY on push to `main` (builds, tags, deploys to Cloud Run)

**Auto-Versioning:**
- Uses conventional commits to auto-bump version (v1.0.0 → v1.0.1, v1.1.0, v2.0.0)
- Creates Git tags and GitHub releases automatically
- Tags Docker images with version numbers

---

## Quick Start

### Prerequisites
- GitHub repo with `main` branch
- Google Cloud Project with billing enabled
- Cloud Run API, Artifact Registry API, IAM API enabled

### 3-Minute Setup
```bash
# 1. Enable required GCP services
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com

# 2. Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Service Account"

# 3. Grant permissions (see GCP Setup for full list)

# 4. Create Artifact Registry repository
gcloud artifacts repositories create subtribe-ats-backend \
  --repository-format=docker \
  --location=asia-south1

# 5. Export service account key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com

# 6. Add GitHub Secrets & Variables (see GitHub Setup)

# 7. Create v1.0.0 tag
git checkout main
git tag v1.0.0
git push origin v1.0.0

# 8. Push to main → Auto-deploy! 🚀
```

---

## GitHub Setup

### Step 1: Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → Secrets**

| Secret Name | Value | Where to Find |
|-------------|-------|---------------|
| `GCP_SA_KEY` | Full JSON content of `github-actions-key.json` | From Step 5 above |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@HOST:5432/postgres` | Supabase Dashboard → Settings → Database → Connection String (replace `postgresql://` with `postgresql+asyncpg://`) |
| `JWT_SECRET_KEY` | Random string (32+ chars) | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SUPABASE_SERVICE_KEY` | `service_role` key | Supabase Dashboard → Settings → API → `service_role` secret |
| `SUPABASE_JWT_SECRET` | JWT secret | Supabase Dashboard → Settings → API → JWT Settings → JWT Secret |

### Step 2: Add GitHub Variables

Go to **Settings → Secrets and variables → Actions → Variables**

| Variable Name | Value | Where to Find |
|---------------|-------|---------------|
| `GCP_PROJECT_ID` | Your GCP project ID | GCP Console → Dashboard |
| `SUPABASE_URL` | `https://YOUR_PROJECT.supabase.co` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | `anon` public key | Supabase Dashboard → Settings → API → `anon` public |
| `GCS_BUCKET_NAME` | `subtribe-ats-resumes-prod` | Your GCS bucket name |
| `GCS_PROJECT_ID` | Your GCP project ID (same as above) | GCP Console → Dashboard |
| `CORS_ORIGINS` | `["https://yourdomain.com"]` | Your frontend URL(s) in JSON array format |

**Important:** 
- Secrets are encrypted, Variables are plain text
- Use Secrets for passwords/keys, Variables for config values
- `CORS_ORIGINS` must be valid JSON array: `["https://app.example.com","https://www.example.com"]`

---

## GCP Setup

### 1. Create Service Account
```bash
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Service Account" \
  --description="Used by GitHub Actions for CI/CD deployment"
```

### 2. Grant Required Permissions
```bash
PROJECT_ID="your-project-id"
SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Artifact Registry permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"

# Service Account User (to deploy as github-actions SA)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Storage permissions (for GCS resume uploads from Cloud Run)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"
```

### 3. Create Artifact Registry Repository
```bash
gcloud artifacts repositories create subtribe-ats-backend \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Docker images for Subtribe ATS Backend"
```

### 4. Export Service Account Key
```bash
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com

# Copy the JSON content and add to GitHub Secrets as GCP_SA_KEY
cat github-actions-key.json
```

### 5. Create GCS Bucket (if not exists)
```bash
gsutil mb -l asia-south1 gs://subtribe-ats-resumes-prod
```

---

## First Deployment (v1.0.0)

### Method 1: Manual Tag (Recommended)
```bash
# Create v1.0.0 tag on main branch
git checkout main
git pull origin main
git tag v1.0.0
git push origin v1.0.0

# Optional: Create GitHub Release
gh release create v1.0.0 \
  --title "v1.0.0 - Initial Release" \
  --notes "🎉 Initial production release"
```

**Next merge will bump from v1.0.0** (v1.0.1, v1.1.0, etc.)

### Method 2: Conventional Commit
When merging your first PR, use this commit message:
```
feat: initial production release

BREAKING CHANGE: first production deployment

- Complete ATS backend implementation
- Authentication and authorization
- Job and application management
```

This will auto-bump v0.0.0 → **v1.0.0** (due to `BREAKING CHANGE:`)

---

## Daily Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/add-email-notifications
# Make changes...
git add .
git commit -m "feat: add email notifications for status changes"
git push origin feature/add-email-notifications
```

### 2. Open Pull Request
- PR triggers `lint-test` job
- Checks linting, formatting, unit tests
- Must pass before merge

### 3. Squash and Merge
When merging PR, use **conventional commit format** in PR title:

**For patch bump (v1.0.0 → v1.0.1):**
```
fix: resolve resume download issue
```

**For minor bump (v1.0.0 → v1.1.0):**
```
feat: add email notifications
```

**For major bump (v1.0.0 → v2.0.0):**
```
feat!: redesign authentication API

BREAKING CHANGE: auth endpoints now require company_id in payload
```

### 4. Auto-Deploy
When you merge to `main`:
1. ✅ `lint-test` job runs
2. ✅ Auto-bumps version (e.g., v1.2.3)
3. ✅ Creates Git tag
4. ✅ Creates GitHub Release
5. ✅ Builds Docker image
6. ✅ Pushes to Artifact Registry (tagged with v1.2.3)
7. ✅ Deploys to Cloud Run
8. ✅ Runs smoke test

**Total time:** ~5-7 minutes from merge to live 🚀

---

## Troubleshooting

### Error: "Resource not accessible by integration"
**Fix:** Workflow now has `permissions: contents: write` at top level. Push the updated workflow.

### Error: "Failed to push Docker image"
**Fix:** Ensure service account has `roles/artifactregistry.writer` permission.

### Error: "Permission denied" on Cloud Run deploy
**Fix:** Ensure service account has `roles/run.admin` and `roles/iam.serviceAccountUser`.

### Error: "No such object" for GCS uploads
**Fix:** Ensure:
- GCS bucket exists: `gsutil ls gs://subtribe-ats-resumes-prod`
- Service account has `roles/storage.objectAdmin`
- Cloud Run service uses `github-actions` service account (check workflow line 103)

### Smoke Test Fails
**Fix:** Check Cloud Run logs:
```bash
gcloud run services logs read subtribe-ats-api --region=asia-south1 --limit=50
```

Common issues:
- Database connection (check `DATABASE_URL` secret)
- Missing environment variables
- Health endpoint not responding

### Version Didn't Bump
**Reason:** Commit message doesn't follow conventional format.

**Fix:** Edit PR title before squash merge:
- ✅ `feat: add new feature`
- ✅ `fix: resolve bug`
- ❌ `add new feature` (no type)
- ❌ `Fixed bug` (wrong case)

---

## Reference

### Commit Types
- `feat:` → Minor bump (v1.0.0 → v1.1.0)
- `fix:` → Patch bump (v1.0.0 → v1.0.1)
- `BREAKING CHANGE:` → Major bump (v1.0.0 → v2.0.0)
- `chore:`, `docs:`, `style:`, `refactor:`, `test:` → Patch bump (default)

### Workflow Files
- `.github/workflows/main.yml` - Main CI/CD pipeline
- `Dockerfile` - Container definition
- `pyproject.toml` - Linter/formatter config
- `requirements.txt` - Python dependencies

### Useful Commands
```bash
# View workflow runs
gh run list --limit 5

# View logs of latest run
gh run view --log

# Manual trigger workflow
gh workflow run main.yml

# List deployed Cloud Run services
gcloud run services list --region=asia-south1

# View Cloud Run service details
gcloud run services describe subtribe-ats-api --region=asia-south1

# View latest Cloud Run logs
gcloud run services logs read subtribe-ats-api --region=asia-south1 --limit=20
```

---

**Questions?** Check the workflow file: `.github/workflows/main.yml`

