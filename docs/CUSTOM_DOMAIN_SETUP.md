# Custom Domain Setup for Subtribe (GCP Cloud Run + Cloudflare)

## Overview

### The Problem
Currently, frontend and backend are on different Cloud Run domains:
- **Frontend**: `subtribe-dashboard-staging-xxx.asia-south1.run.app`
- **Backend**: `subtribe-backend-staging-xxx.asia-south1.run.app`

Browsers block cookies between different domains (third-party cookie blocking).

### The Solution
Put both services on the same root domain (`thesubtribe.com`):
- **Frontend**: `dashboard-staging.thesubtribe.com` / `dashboard.thesubtribe.com`
- **Backend**: `api-staging.thesubtribe.com` / `api.thesubtribe.com`

Now cookies with `domain=.thesubtribe.com` work across both subdomains.

### Region: asia-east1 (Taiwan)

We use `asia-east1` (Taiwan) because it **supports custom domain mappings** and is closest to India.

Note: `asia-south1` (Mumbai) does NOT support custom domain mappings.
See: https://cloud.google.com/run/docs/mapping-custom-domains

---

## Final URLs

| Service | Staging | Production |
|---------|---------|------------|
| **Frontend** | `https://dashboard-staging.thesubtribe.com` | `https://dashboard.thesubtribe.com` |
| **Backend** | `https://api-staging.thesubtribe.com` | `https://api.thesubtribe.com` |

---

## Step-by-Step Plan

### Phase 1: Create Artifact Registry in asia-east1 (5 min)

```bash
# Check if it already exists
gcloud artifacts repositories list --location=asia-east1

# If not, create it
gcloud artifacts repositories create subtribe \
  --repository-format=docker \
  --location=asia-east1 \
  --description="Subtribe Docker images"
```

---

### Phase 2: Deploy Services to New Region (10 min)

The workflow files have been updated to use `asia-east1`. Deploy to create services in the new region:

```bash
# Backend - push to staging or trigger manual deploy
cd subtribe-backend
git add .github/workflows/
git commit -m "chore: migrate to asia-east1 for custom domain support"
git push origin staging

# Dashboard - push to staging or trigger manual deploy
cd subtribe-dashboard
git add .github/workflows/
git commit -m "chore: migrate to asia-east1 for custom domain support"
git push origin staging
```

Or trigger manually via GitHub Actions.

---

### Phase 3: Add GCP Domain Mappings (10 min)

Now that services are in asia-east1, add custom domain mappings.

#### Via gcloud CLI (Recommended)

```bash
# Backend Staging
gcloud beta run domain-mappings create \
  --service=subtribe-backend-staging \
  --domain=api-staging.thesubtribe.com \
  --region=asia-east1

# Frontend Staging
gcloud beta run domain-mappings create \
  --service=subtribe-dashboard-staging \
  --domain=dashboard-staging.thesubtribe.com \
  --region=asia-east1

# Backend Production
gcloud beta run domain-mappings create \
  --service=subtribe-backend-prod \
  --domain=api.thesubtribe.com \
  --region=asia-east1

# Frontend Production
gcloud beta run domain-mappings create \
  --service=subtribe-dashboard-prod \
  --domain=dashboard.thesubtribe.com \
  --region=asia-east1
```

#### Via GCP Console

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on service (e.g., `subtribe-backend-staging`)
3. Click **"Integrations"** tab
4. Click **"Add Integration"** → **"Custom domain"**
5. Enter domain (e.g., `api-staging.thesubtribe.com`)
6. Click **"Submit"**
7. Note the DNS records shown
8. Repeat for all 4 services

---

### Phase 4: Configure Cloudflare DNS (10 min)

#### Step 4.1: Access Cloudflare DNS

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select `thesubtribe.com`
3. Click **"DNS"** in left sidebar
4. Click **"Records"**

#### Step 4.2: Add DNS Records

Add these CNAME records (proxy **OFF** - grey cloud):

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `api-staging` | `ghs.googlehosted.com` | **OFF** (grey) |
| CNAME | `dashboard-staging` | `ghs.googlehosted.com` | **OFF** (grey) |
| CNAME | `api` | `ghs.googlehosted.com` | **OFF** (grey) |
| CNAME | `dashboard` | `ghs.googlehosted.com` | **OFF** (grey) |

**IMPORTANT**: Proxy MUST be **OFF** (grey cloud). GCP handles SSL certificates.

---

### Phase 5: Wait for SSL Certificates (5-30 min)

GCP automatically provisions SSL certificates.

#### Check Status via CLI

```bash
gcloud beta run domain-mappings list --region=asia-east1
```

#### Check Status via Console

1. Go to Cloud Run → Service → Integrations
2. Look for status: **"Active"** = Ready!

Wait until all 4 show "Active" before proceeding.

---

### Phase 6: Update GitHub Variables - Backend Repository (10 min)

Go to: **GitHub → subtribe-backend → Settings → Environments**

#### Step 6.1: Update Staging Environment Variables

1. Click **"Staging"** environment
2. Under **"Environment variables"**, update:

| Variable | New Value |
|----------|-----------|
| `DASHBOARD_URL` | `https://dashboard-staging.thesubtribe.com` |
| `BACKEND_URL` | `https://api-staging.thesubtribe.com` |
| `ALLOWED_ORIGINS` | `["https://dashboard-staging.thesubtribe.com","http://localhost:3000"]` |

#### Step 6.2: Update Production Environment Variables

1. Click **"Production"** environment
2. Under **"Environment variables"**, update:

| Variable | New Value |
|----------|-----------|
| `DASHBOARD_URL` | `https://dashboard.thesubtribe.com` |
| `BACKEND_URL` | `https://api.thesubtribe.com` |
| `ALLOWED_ORIGINS` | `["https://dashboard.thesubtribe.com"]` |
| `COOKIE_DOMAIN` | `.thesubtribe.com` |

---

### Phase 7: Update GitHub Variables - Dashboard Repository (10 min)

Go to: **GitHub → subtribe-dashboard → Settings → Environments**

#### Step 7.1: Update Staging Environment Variables

1. Click **"Staging"** environment
2. Under **"Environment variables"**, update:

| Variable | New Value |
|----------|-----------|
| `NEXT_PUBLIC_API_URL` | `https://api-staging.thesubtribe.com` |
| `NEXT_PUBLIC_BASE_URL` | `https://dashboard-staging.thesubtribe.com` |
| `NEXT_PUBLIC_APP_URL` | `https://dashboard-staging.thesubtribe.com` |

#### Step 7.2: Update Production Environment Variables

1. Click **"Production"** environment
2. Under **"Environment variables"**, update:

| Variable | New Value |
|----------|-----------|
| `NEXT_PUBLIC_API_URL` | `https://api.thesubtribe.com` |
| `NEXT_PUBLIC_BASE_URL` | `https://dashboard.thesubtribe.com` |
| `NEXT_PUBLIC_APP_URL` | `https://dashboard.thesubtribe.com` |

---

### Phase 8: Update Backend Workflow Files (5 min)

These changes update cookie configuration for same-site authentication.

#### Step 8.1: Edit `deploy-staging.yml`

File: `.github/workflows/deploy-staging.yml`

Find lines ~191-195 and change:
```yaml
# Cookie Configuration (HTTP-only cookie authentication)
COOKIE_SECURE: "true"
COOKIE_SAMESITE: "Lax"              # Changed from "None"
COOKIE_DOMAIN: ".thesubtribe.com"   # Changed from ""
COOKIE_MAX_AGE: "2592000"
```

#### Step 8.2: Edit `manual-deploy-staging.yml`

File: `.github/workflows/manual-deploy-staging.yml`

Find lines ~213-216 and change:
```yaml
# Cookie Configuration (HTTP-only cookie authentication)
COOKIE_SECURE: "true"
COOKIE_SAMESITE: "Lax"              # Changed from "None"
COOKIE_DOMAIN: ".thesubtribe.com"   # Changed from ""
COOKIE_MAX_AGE: "2592000"
```

#### Step 8.3: Edit `deploy-prod.yml`

File: `.github/workflows/deploy-prod.yml`

Find lines ~217-220 and change:
```yaml
# Cookie Configuration (HTTP-only cookie authentication)
COOKIE_SECURE: "true"
COOKIE_SAMESITE: "Lax"              # Changed from "None"
COOKIE_DOMAIN: "${{ vars.COOKIE_DOMAIN }}"
COOKIE_MAX_AGE: "2592000"
```

#### Step 8.4: Commit Workflow Changes

```bash
cd subtribe-backend
git add .github/workflows/
git commit -m "feat: update cookie config for custom domains"
git push origin staging  # or main for production
```

---

### Phase 9: Redeploy Services (10 min)

#### Step 9.1: Deploy Backend Staging

Option A: Push to staging branch (triggers automatic deploy)
```bash
cd subtribe-backend
git checkout staging
git push origin staging
```

Option B: Manual trigger via GitHub Actions
1. Go to GitHub → subtribe-backend → Actions
2. Click "Manual Deploy to Staging"
3. Click "Run workflow"

#### Step 9.2: Deploy Frontend Staging

Option A: Push to staging branch
```bash
cd subtribe-dashboard
git checkout staging
git push origin staging
```

Option B: Manual trigger via GitHub Actions

#### Step 9.3: Wait for Deployments

Monitor GitHub Actions to ensure both deployments succeed.

---

### Phase 10: Test Staging (10 min)

#### Step 10.1: Clear Browser Data

1. Open browser DevTools (F12)
2. Go to **Application** → **Cookies**
3. Delete all cookies for `thesubtribe.com`
4. Also clear `subtribe-backend-staging-xxx.run.app` cookies if present

#### Step 10.2: Test Sign-In Flow

1. Go to `https://dashboard-staging.thesubtribe.com`
2. Sign in with test account
3. Open DevTools → **Application** → **Cookies**
4. Verify `access_token` cookie exists with:
   - **Domain**: `.thesubtribe.com`
   - **Path**: `/`
   - **HttpOnly**: `true`
   - **Secure**: `true`
   - **SameSite**: `Lax`

#### Step 10.3: Test Protected Routes

1. Navigate to dashboard pages
2. Refresh the page - should stay logged in
3. Check Network tab - `/auth/me` should return 200

#### Step 10.4: Test Logout

1. Click logout
2. Verify cookie is removed
3. Verify redirect to sign-in page

---

### Phase 11: Deploy Production (after staging works)

Repeat Phase 9 for production:
1. Merge to `main` branch or trigger production deploy
2. Test at `https://dashboard.thesubtribe.com`

---

## Troubleshooting

### Domain mapping stuck on "Pending"

1. Verify Cloudflare DNS record exists
2. Verify proxy is OFF (grey cloud, not orange)
3. Verify target is exactly `ghs.googlehosted.com`
4. Wait up to 1 hour, then check GCP console for errors

### SSL certificate failed

1. Same checks as above
2. Delete the domain mapping in GCP and re-add it
3. Ensure no CAA records in Cloudflare DNS blocking Google

### Cookies not being set

1. Check browser DevTools → Network → Response Headers
2. Look for `Set-Cookie` header
3. Verify `COOKIE_DOMAIN` is `.thesubtribe.com` (with leading dot)
4. Verify `ALLOWED_ORIGINS` includes the frontend URL

### 401 on /auth/me

1. Check if cookie is being sent (DevTools → Network → Request Headers)
2. Verify cookie domain matches
3. Check backend logs in GCP Cloud Run

### Old URLs still working

This is expected - Cloud Run keeps `.run.app` URLs active. You can disable them later in Cloud Run settings if needed.

---

## Rollback Plan

If something goes wrong:

1. **Revert GitHub variables** to old Cloud Run URLs
2. **Revert workflow files** - change `COOKIE_SAMESITE` back to `"None"` and `COOKIE_DOMAIN` back to `""`
3. **Redeploy** both services
4. Old `.run.app` URLs will continue working

---

## Complete Checklist

### GCP Cloud Run
- [ ] Domain mapping: `api-staging.thesubtribe.com` → `subtribe-backend-staging`
- [ ] Domain mapping: `dashboard-staging.thesubtribe.com` → `subtribe-dashboard-staging`
- [ ] Domain mapping: `api.thesubtribe.com` → `subtribe-backend-prod`
- [ ] Domain mapping: `dashboard.thesubtribe.com` → `subtribe-dashboard-prod`

### Cloudflare DNS
- [ ] CNAME: `api-staging` → `ghs.googlehosted.com` (proxy OFF)
- [ ] CNAME: `dashboard-staging` → `ghs.googlehosted.com` (proxy OFF)
- [ ] CNAME: `api` → `ghs.googlehosted.com` (proxy OFF)
- [ ] CNAME: `dashboard` → `ghs.googlehosted.com` (proxy OFF)

### SSL Certificates (wait for "Active" status)
- [ ] `api-staging.thesubtribe.com` - Active
- [ ] `dashboard-staging.thesubtribe.com` - Active
- [ ] `api.thesubtribe.com` - Active
- [ ] `dashboard.thesubtribe.com` - Active

### GitHub Variables - Backend
- [ ] Staging: `DASHBOARD_URL` = `https://dashboard-staging.thesubtribe.com`
- [ ] Staging: `BACKEND_URL` = `https://api-staging.thesubtribe.com`
- [ ] Staging: `ALLOWED_ORIGINS` = `["https://dashboard-staging.thesubtribe.com","http://localhost:3000"]`
- [ ] Production: `DASHBOARD_URL` = `https://dashboard.thesubtribe.com`
- [ ] Production: `BACKEND_URL` = `https://api.thesubtribe.com`
- [ ] Production: `ALLOWED_ORIGINS` = `["https://dashboard.thesubtribe.com"]`
- [ ] Production: `COOKIE_DOMAIN` = `.thesubtribe.com`

### GitHub Variables - Dashboard
- [ ] Staging: `NEXT_PUBLIC_API_URL` = `https://api-staging.thesubtribe.com`
- [ ] Staging: `NEXT_PUBLIC_BASE_URL` = `https://dashboard-staging.thesubtribe.com`
- [ ] Staging: `NEXT_PUBLIC_APP_URL` = `https://dashboard-staging.thesubtribe.com`
- [ ] Production: `NEXT_PUBLIC_API_URL` = `https://api.thesubtribe.com`
- [ ] Production: `NEXT_PUBLIC_BASE_URL` = `https://dashboard.thesubtribe.com`
- [ ] Production: `NEXT_PUBLIC_APP_URL` = `https://dashboard.thesubtribe.com`

### Workflow Files - Backend
- [ ] `deploy-staging.yml`: `COOKIE_SAMESITE: "Lax"`, `COOKIE_DOMAIN: ".thesubtribe.com"`
- [ ] `manual-deploy-staging.yml`: `COOKIE_SAMESITE: "Lax"`, `COOKIE_DOMAIN: ".thesubtribe.com"`
- [ ] `deploy-prod.yml`: `COOKIE_SAMESITE: "Lax"`

### Deployments
- [ ] Backend staging deployed
- [ ] Frontend staging deployed
- [ ] Staging tested and working
- [ ] Backend production deployed
- [ ] Frontend production deployed
- [ ] Production tested and working

---

## Summary Diagram

```
BEFORE (broken - third-party cookies blocked):
┌─────────────────────────────────────────────────┐
│ Browser                                         │
│                                                 │
│  subtribe-dashboard-staging-xxx.run.app         │
│         │                                       │
│         │ fetch (credentials: include)          │
│         ▼                                       │
│  subtribe-backend-staging-xxx.run.app           │
│         │                                       │
│         │ Set-Cookie (blocked by browser)       │
│         ▼                                       │
│  ❌ BLOCKED - different domains                 │
└─────────────────────────────────────────────────┘

AFTER (working - same root domain):
┌─────────────────────────────────────────────────┐
│ Browser                                         │
│                                                 │
│  dashboard-staging.thesubtribe.com              │
│         │                                       │
│         │ fetch (credentials: include)          │
│         ▼                                       │
│  api-staging.thesubtribe.com                    │
│         │                                       │
│         │ Set-Cookie (domain=.thesubtribe.com)  │
│         ▼                                       │
│  ✅ ALLOWED - same root domain                  │
└─────────────────────────────────────────────────┘
```
