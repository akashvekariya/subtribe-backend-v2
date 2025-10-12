# Deployment

CI/CD pipeline and production deployment to Google Cloud Run.

---

## Overview

**Platform**: Google Cloud Run (serverless)  
**CI/CD**: GitHub Actions  
**Versioning**: Semantic versioning (automated)  
**Registry**: Google Artifact Registry

**Workflow**: `.github/workflows/main.yml`

---

## Architecture

### Pipeline Jobs

**1. Lint & Test**
- Runs on all pushes and pull requests
- Linting with Ruff
- Unit tests with pytest
- Database-dependent tests with PostgreSQL service

**2. Deploy**
- Runs only on push to `main` branch
- Semantic version bump (conventional commits)
- Docker image build and push
- Cloud Run deployment
- GitHub Release creation

---

## GitHub Setup

### Secrets

Navigate to **Settings → Secrets and variables → Actions → Secrets**

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON key (full content) |
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Backend JWT secret (32+ chars) |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret |

### Variables

Navigate to **Settings → Secrets and variables → Actions → Variables**

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon public key |
| `GCS_BUCKET_NAME` | GCS bucket name (production) |
| `GCS_PROJECT_ID` | GCP project ID (same as above) |
| `CORS_ORIGINS` | Allowed origins (e.g., `*` or `https://app.example.com`) |

---

## GCP Setup

### 1. Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com
```

### 2. Create Service Account
```bash
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD"
```

### 3. Grant Permissions
```bash
PROJECT_ID="your-project-id"
SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Artifact Registry Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.admin"

# Storage Object Admin (for GCS)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"
```

### 4. Create Artifact Registry
```bash
gcloud artifacts repositories create subtribe-ats-backend \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Subtribe ATS Docker images"
```

### 5. Export Service Account Key
```bash
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=$SA_EMAIL
```

**⚠️ Security**: Store this key securely in GitHub Secrets as `GCP_SA_KEY`.

---

## Semantic Versioning

### Conventional Commits

Version bumps based on commit message prefixes:

| Prefix | Version Bump | Example |
|--------|--------------|---------|
| `fix:` | Patch (0.0.X) | `fix: resolve login issue` |
| `feat:` | Minor (0.X.0) | `feat: add export functionality` |
| `BREAKING CHANGE:` | Major (X.0.0) | `feat!: redesign API` or commit body contains `BREAKING CHANGE:` |

### Squash and Merge

**Required**: Enable "Squash and Merge" in GitHub repo settings

**Why?** Multiple commits in a PR are squashed into one with a clean message, making version bumping predictable.

**Workflow**:
1. Create PR with any commits
2. When merging, edit squash commit message to follow convention
3. Merge to `main`
4. CI automatically bumps version and deploys

---

## Deployment Process

### Automatic Deployment

Triggered on merge to `main`:

1. **Lint & Test** job runs
   - Ruff checks code quality
   - Pytest runs unit tests
2. **Deploy** job runs (after tests pass)
   - Bumps version based on commit message
   - Creates Git tag (e.g., `v1.0.1`)
   - Builds Docker image
   - Pushes to Artifact Registry
   - Deploys to Cloud Run
   - Creates GitHub Release

### Manual Deployment

Trigger from GitHub Actions UI:

1. Go to **Actions** tab
2. Select "CI/CD Pipeline" workflow
3. Click "Run workflow"
4. Select branch
5. Click "Run workflow"

**Note**: Manual runs also deploy after tests pass.

---

## First Release (v1.0.0)

### Option 1: Manual Tag (Recommended)
```bash
git checkout main
git tag v1.0.0
git push origin v1.0.0
```

### Option 2: Breaking Change Commit
```bash
git commit -m "feat!: initial release

BREAKING CHANGE: First production release"
```

---

## Cloud Run Configuration

### Environment Variables

Set in workflow (`.github/workflows/main.yml`):

```yaml
--set-env-vars \
  ENVIRONMENT=production,\
  DATABASE_URL=${{ secrets.DATABASE_URL }},\
  JWT_SECRET_KEY=${{ secrets.JWT_SECRET_KEY }},\
  SUPABASE_URL=${{ vars.SUPABASE_URL }},\
  SUPABASE_ANON_KEY=${{ vars.SUPABASE_ANON_KEY }},\
  SUPABASE_SERVICE_KEY=${{ secrets.SUPABASE_SERVICE_KEY }},\
  SUPABASE_JWT_SECRET=${{ secrets.SUPABASE_JWT_SECRET }},\
  GCS_BUCKET_NAME=${{ vars.GCS_BUCKET_NAME }},\
  GCS_PROJECT_ID=${{ vars.GCS_PROJECT_ID }},\
  CORS_ORIGINS=${{ vars.CORS_ORIGINS }}
```

### Service Configuration

- **Region**: asia-south1 (Mumbai)
- **CPU**: 1
- **Memory**: 512Mi
- **Max Instances**: 100 (auto-scaling)
- **Timeout**: 300s
- **Port**: 8080

### Service Account

Cloud Run uses the GitHub Actions service account for:
- Accessing GCS (Application Default Credentials)
- Other GCP services

**No `GOOGLE_APPLICATION_CREDENTIALS` needed** - ADC handles authentication automatically.

---

## Docker Image

### Multi-Stage Build

**Dockerfile**:
```dockerfile
# Builder stage
FROM python:3.13-slim as builder
# ... install dependencies

# Runtime stage
FROM python:3.13-slim
# ... copy only what's needed
```

**Benefits**:
- Smaller final image (~150MB)
- Faster deployments
- Better security (no build tools in production)

### Image Tagging

Images are tagged with:
- Semantic version: `v1.0.1`
- Git SHA: `abc1234`
- Latest: `latest`

---

## Monitoring

### Cloud Run Logs
```bash
# View logs
gcloud run logs read subtribe-ats-backend \
  --region asia-south1 \
  --limit 100

# Stream logs
gcloud run logs tail subtribe-ats-backend \
  --region asia-south1
```

### Health Check
```bash
# Check service status
gcloud run services describe subtribe-ats-backend \
  --region asia-south1

# Test health endpoint
curl https://your-service-url.run.app/health
```

### Metrics

View in GCP Console:
- Request count
- Request latency
- Error rate
- Instance count
- CPU/Memory usage

---

## Rollback

### Revert to Previous Version

```bash
# List revisions
gcloud run revisions list \
  --service subtribe-ats-backend \
  --region asia-south1

# Route traffic to previous revision
gcloud run services update-traffic subtribe-ats-backend \
  --to-revisions REVISION_NAME=100 \
  --region asia-south1
```

### Redeploy Previous Version

```bash
# Deploy specific image
gcloud run deploy subtribe-ats-backend \
  --image asia-south1-docker.pkg.dev/PROJECT/subtribe-ats-backend/subtribe-ats-backend:v1.0.0 \
  --region asia-south1
```

---

## Cost Optimization

### Current Costs

**Estimated for 100k requests/month**:
- Cloud Run: ~$20/month
- Artifact Registry: ~$5/month
- **Total**: ~$25/month

### Optimization Tips

1. **Reduce cold starts**: Keep min instances = 1 (costs ~$10/month extra)
2. **Optimize images**: Multi-stage builds, slim base images
3. **Connection pooling**: Reuse database connections
4. **Caching**: Add Redis for hot data (future)

---

## Troubleshooting

### Deployment Fails

**Check workflow logs**:
1. Go to Actions tab
2. Click failed workflow
3. Expand failed step
4. Read error message

**Common issues**:
- Missing secrets/variables
- Invalid service account permissions
- Image build failures
- Database connection errors

### Service Won't Start

**Check Cloud Run logs**:
```bash
gcloud run logs read subtribe-ats-backend --limit 50
```

**Common issues**:
- Missing environment variables
- Database connection timeout
- Port mismatch (must be 8080)
- Startup timeout (increase if needed)

### Image Push Fails

**Authenticate Docker**:
```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

**Check Artifact Registry permissions**:
```bash
gcloud artifacts repositories get-iam-policy subtribe-ats-backend \
  --location asia-south1
```

---

## Security Best Practices

1. **Secrets**: Never commit secrets to git
2. **Service Account**: Least privilege principle
3. **HTTPS**: Enforced by Cloud Run (automatic)
4. **Environment Variables**: Use GitHub Secrets for sensitive data
5. **Image Scanning**: Enable in Artifact Registry settings
6. **Dependencies**: Regular updates with Dependabot

---

**Related**:
- [Architecture](Architecture)
- [Development](Development)
- [API Reference](API-Reference)

