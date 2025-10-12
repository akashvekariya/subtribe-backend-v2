# GitHub Actions Setup Guide

This guide explains how to configure GitHub Actions for continuous integration (CI) and continuous deployment (CD).

## 📋 Prerequisites

Before setting up GitHub Actions, ensure you have:

1. **GitHub Repository**: Code pushed to GitHub
2. **Google Cloud Project**: Created and configured
3. **Google Cloud Run**: Service account with permissions
4. **Supabase Project**: Production database ready
5. **GCS Bucket**: Created for production

---

## 🔧 Part 1: Local Setup & Testing

### Step 1: Install Development Dependencies

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Install all dependencies including linting tools
pip install -r requirements.txt
```

### Step 2: Test Linting Locally

```bash
# Run Ruff linter (checks for errors)
ruff check .

# Auto-fix issues that can be fixed automatically
ruff check . --fix

# Check code formatting
ruff format --check .

# Format code automatically
ruff format .

# Run type checker (optional, may show many warnings initially)
mypy app/ --ignore-missing-imports
```

### Step 3: Test Locally Before Pushing

```bash
# Run unit tests (same as CI will run)
pytest tests/unit/ -v

# Run all checks together (simulate CI)
ruff check . && \
ruff format --check . && \
pytest tests/unit/ -v && \
echo "✅ All checks passed! Safe to push."
```

**Expected Result**: All checks should pass locally before you push to GitHub.

---

## 🚀 Part 2: GitHub Actions - CI Setup

The CI workflow (`.github/workflows/ci.yml`) runs automatically on:
- **Pull Requests** to `main`, `develop`, or `develop/v1`
- **Pushes** to `main`, `develop`, or `develop/v1`

### What CI Does:

1. ✅ **Lints code** with Ruff (checks for errors)
2. ✅ **Checks formatting** with Ruff
3. ✅ **Type checks** with mypy (optional, doesn't fail build)
4. ✅ **Runs unit tests** with pytest

### How to View CI Results:

1. Push code or create a Pull Request
2. Go to GitHub → Your Repo → **Actions** tab
3. Click on the running workflow
4. View logs for each step

**No additional setup needed** - CI works out of the box!

---

## 🚀 Part 3: GitHub Actions - CD Setup (Deployment)

The CD workflow (`.github/workflows/deploy.yml`) deploys to Google Cloud Run when you push to `main`.

### Prerequisites:

#### 1. Create Google Cloud Service Account

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Deployment"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Generate JSON key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com
```

**⚠️ Important**: Keep `github-actions-key.json` secure! Add it to GitHub Secrets (next step).

#### 2. Create Artifact Registry Repository

```bash
# Create repository for Docker images
gcloud artifacts repositories create subtribe-ats-backend \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Docker repository for Subtribe ATS"
```

#### 3. Create Secret Manager Secret for GCS Credentials

```bash
# Upload your GCS service account JSON to Secret Manager
gcloud secrets create gcs-credentials \
  --data-file=secrets/subtribe-ats-storage-key.json \
  --replication-policy="automatic"

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding gcs-credentials \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 1: Add GitHub Secrets & Variables

Go to GitHub → Your Repo → **Settings** → **Secrets and variables** → **Actions**

#### Add Secrets (Encrypted - Contains Passwords/Keys)

Click **"New repository secret"** and add these:

| Secret Name | Value | Where to Find |
|------------|-------|---------------|
| `GCP_SA_KEY` | Contents of `github-actions-key.json` | Generated in step above |
| `DATABASE_URL` | Production database URL | Supabase → Settings → Database → Connection String (use `postgresql+asyncpg://`) |
| `JWT_SECRET_KEY` | Secret key for JWT | Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Supabase → Settings → API → service_role (secret) |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret | Supabase → Settings → API → JWT Secret |

⚠️ **Important:** These MUST be secrets (encrypted) as they contain passwords/keys!

#### Add Variables (Plain Text - Non-Sensitive Configuration)

Click **"Variables"** tab, then **"New repository variable"** and add these:

| Variable Name | Value | Where to Find |
|------------|-------|---------------|
| `GCP_PROJECT_ID` | Your GCP project ID | GCP Console → Project Info |
| `SUPABASE_URL` | Production Supabase URL | Supabase → Settings → API → URL |
| `SUPABASE_ANON_KEY` | Supabase anon key | Supabase → Settings → API → anon public |
| `GCS_BUCKET_NAME` | Production GCS bucket | `subtribe-ats-resumes-prod` |
| `GCS_PROJECT_ID` | GCP project for GCS | Same as `GCP_PROJECT_ID` |
| `CORS_ORIGINS` | Allowed origins (JSON array) | `["https://yourdomain.com"]` |

✅ **Note:** These are safe as variables since they're public or non-sensitive configuration.

### Step 2: Test Deployment Manually

Before pushing to `main`, test deployment manually:

1. Go to GitHub → Your Repo → **Actions**
2. Click "CD - Deploy to Cloud Run"
3. Click "Run workflow" → Select `main` branch → "Run workflow"
4. Watch the logs

### Step 3: Automatic Deployments

Once manual deployment works:
- Every push to `main` will automatically deploy to Cloud Run
- Check the Actions tab to monitor deployments

---

## 🛡️ Security Best Practices

### 1. Branch Protection Rules

Set up branch protection for `main`:

1. GitHub → Repo → **Settings** → **Branches**
2. Add rule for `main`:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass (select "Lint & Test")
   - ✅ Require branches to be up to date
   - ✅ Do not allow bypassing the above settings

**Result**: Can't merge to `main` unless CI passes.

### 2. Environment Protection

For extra safety, create a GitHub Environment:

1. GitHub → Repo → **Settings** → **Environments** → **New environment**
2. Name: `production`
3. Add protection rules:
   - ✅ Required reviewers (add yourself)
   - ✅ Wait timer (optional - e.g., 5 minutes)

Update `.github/workflows/deploy.yml`:
```yaml
jobs:
  deploy:
    environment: production  # Add this line
    # ... rest of config
```

**Result**: Deployments require manual approval.

---

## 📊 Monitoring Deployments

### View Deployment Status

1. **GitHub Actions**: GitHub → Actions → View workflow runs
2. **Cloud Run**: GCP Console → Cloud Run → Select service
3. **Logs**: Cloud Run → Logs tab

### Rollback if Needed

```bash
# List revisions
gcloud run revisions list --service=subtribe-ats-api --region=asia-south1

# Rollback to previous revision
gcloud run services update-traffic subtribe-ats-api \
  --to-revisions=REVISION_NAME=100 \
  --region=asia-south1
```

---

## 🐛 Troubleshooting

### CI Fails with "Ruff not found"

**Solution**: Make sure `ruff>=0.1.0` is in `requirements.txt`

### CD Fails with "Permission denied"

**Solution**: Check service account has correct IAM roles (run.admin, iam.serviceAccountUser)

### Deployment succeeds but app crashes

**Solution**: 
1. Check Cloud Run logs
2. Verify all environment variables are set correctly
3. Test Docker image locally: `docker run -p 8080:8080 IMAGE_NAME`

### Health check fails after deployment

**Solution**: 
1. Check Cloud Run logs for startup errors
2. Verify database connection string is correct
3. Ensure all secrets are properly configured

---

## 📚 Additional Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Deployment Guide](https://cloud.google.com/run/docs/deploying)

---

## 🎯 Quick Checklist

**Before first deployment**:
- [ ] All secrets added to GitHub
- [ ] Service account created with correct permissions
- [ ] Artifact Registry repository created
- [ ] Secret Manager secret created for GCS credentials
- [ ] Tested CI locally (`ruff check . && pytest`)
- [ ] Branch protection rules set up

**For each deployment**:
- [ ] Code pushed to GitHub
- [ ] CI passes (green checkmark)
- [ ] Create PR to `main`
- [ ] Review and merge PR
- [ ] CD automatically deploys
- [ ] Health check passes
- [ ] Test production endpoint

---

**Need help?** Check the GitHub Actions logs for detailed error messages.

