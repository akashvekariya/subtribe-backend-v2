# Semantic Versioning Guide

## Recommended Workflow: Squash and Merge

**Enable in GitHub Settings:**
1. Go to Repo → **Settings** → **General** → **Pull Requests**
2. ✅ Enable **"Allow squash merging"**
3. ✅ Set default to **"Default to PR title for squash merge commits"**
4. ❌ Optionally disable other merge methods (for consistency)

**Benefits:**
- ✅ Messy work-in-progress commits stay in feature branch
- ✅ Clean, single commit on main with proper conventional message
- ✅ One commit = one release version
- ✅ Easy to understand git history

---

## How It Works

Every time you **squash merge** to `main`, the CI/CD automatically:
1. **Analyzes commit message** (the squashed commit)
2. **Bumps version** based on commit type
3. **Creates Git tag** (e.g., `v1.2.3`)
4. **Creates GitHub Release** with changelog
5. **Tags Docker image** with version
6. **Deploys versioned image** to Cloud Run

---

## Conventional Commit Format

```
<type>: <short description>

<optional longer description>

<optional footer>
```

### Commit Types (Determines Version Bump)

| Commit Type | Version Bump | Example | Result |
|-------------|--------------|---------|--------|
| `feat:` | **Minor** (v1.0.0 → v1.1.0) | `feat: add job search endpoint` | New feature |
| `fix:` | **Patch** (v1.0.0 → v1.0.1) | `fix: resolve resume upload bug` | Bug fix |
| `BREAKING CHANGE:` | **Major** (v1.0.0 → v2.0.0) | `feat!: redesign auth API` | Breaking change |
| `chore:`, `docs:`, etc. | **Patch** (default) | `chore: update dependencies` | Other changes |

---

## Examples

### Minor Release (New Feature)

```bash
git commit -m "feat: add candidate search filtering

- Added search by skills
- Added search by experience level
- Updated API documentation
"
```
**Result:** v1.0.0 → **v1.1.0**

---

### Patch Release (Bug Fix)

```bash
git commit -m "fix: prevent duplicate application submissions

Added email + job_id unique constraint to applications table
"
```
**Result:** v1.1.0 → **v1.1.1**

---

### Major Release (Breaking Change)

```bash
git commit -m "feat!: redesign authentication API

BREAKING CHANGE: Auth endpoints now use JWT instead of sessions.
Clients must update to use Authorization header.
"
```
**Result:** v1.1.1 → **v2.0.0**

Or use footer:

```bash
git commit -m "refactor: change job status enum values

Changed status values from numbers to strings for clarity.

BREAKING CHANGE: Job status API responses now return strings
instead of integers. Update frontend to handle new format.
"
```
**Result:** v1.1.1 → **v2.0.0**

---

### Multiple Commits in PR

If your PR has multiple commits:
- **Highest priority change** determines version bump
- `BREAKING CHANGE` > `feat` > `fix`

Example PR commits:
```
fix: resolve email validation bug
feat: add job archiving feature
chore: update dependencies
```
**Result:** v1.0.0 → **v1.1.0** (feat wins)

---

## Other Conventional Commit Types

| Type | Description | Version Bump |
|------|-------------|--------------|
| `build:` | Build system changes | Patch |
| `chore:` | Maintenance tasks | Patch |
| `ci:` | CI/CD changes | Patch |
| `docs:` | Documentation only | Patch |
| `style:` | Code style/formatting | Patch |
| `refactor:` | Code refactoring | Patch |
| `perf:` | Performance improvements | Patch |
| `test:` | Adding/fixing tests | Patch |

---

## Checking Current Version

**In GitHub:**
- Go to **Releases** tab
- Latest release shows current version

**In Terminal:**
```bash
git describe --tags --abbrev=0
```

**In Logs:**
Every deployment shows: `📦 Version: v1.2.3`

---

## Viewing Docker Images by Version

```bash
# List all versions in Artifact Registry
gcloud artifacts docker images list \
  asia-south1-docker.pkg.dev/soy-lore-473615-m9/subtribe-ats-backend/subtribe-ats-api

# Pull specific version
docker pull asia-south1-docker.pkg.dev/soy-lore-473615-m9/subtribe-ats-backend/subtribe-ats-api:v1.2.3
```

---

## Rolling Back to Previous Version

If deployment has issues:

```bash
# Deploy previous version
gcloud run deploy subtribe-ats-api \
  --image=asia-south1-docker.pkg.dev/soy-lore-473615-m9/subtribe-ats-backend/subtribe-ats-api:v1.2.2 \
  --region=asia-south1
```

Or use GitHub Actions UI:
1. **Actions** tab → **CD - Deploy to Cloud Run**
2. Click **"Run workflow"**
3. Manually specify version tag

---

## Best Practices

1. **One feature per commit** when possible
2. **Use descriptive messages** - helps generate changelog
3. **Mark breaking changes explicitly** - critical for API consumers
4. **Squash PR commits** for cleaner history (optional)

---

## Example Workflow (Squash and Merge)

**Feature branch with messy commits:**
```bash
# Work on feature branch
git checkout -b feature/candidate-filters

# Make changes with any commit messages (no need to be perfect!)
git commit -m "wip"
git commit -m "add filter logic"
git commit -m "fix typo"
git commit -m "update tests"
git commit -m "more fixes"
git commit -m "done"

# Push and create PR
git push origin feature/candidate-filters
```

**On GitHub:**
1. Create Pull Request: `feature/candidate-filters` → `main`
2. Set PR title: `feat: add experience level filter to candidate search`
3. CI runs and passes ✅
4. Click **"Squash and merge"**
5. GitHub shows merge commit message (uses PR title)
6. Edit if needed, ensure it follows conventional format:
   ```
   feat: add experience level filter to candidate search
   
   - Added filters for junior, mid, senior levels
   - Updated API documentation
   - Added comprehensive tests
   ```
7. Click **"Confirm squash and merge"**

**Result:**
- ✅ All 6 messy commits squashed into ONE clean commit on main
- ✅ Automatic version bump: v1.2.0 → **v1.3.0**
- ✅ GitHub Release created with changelog
- ✅ Docker image tagged as v1.3.0
- ✅ Deployed to production automatically

---

## Manual Version Override

If needed, you can manually create a tag:

```bash
# Create specific version
git tag v2.0.0
git push origin v2.0.0
```

Next merge will continue from this version.

---

**Current Setup:**
- ✅ Auto-versioning on every merge to main
- ✅ GitHub Releases with changelog
- ✅ Docker images tagged with version
- ✅ Cloud Run deploys specific versions
- ✅ Easy rollback to any previous version

---

## Quick Start Checklist

Before your first deployment:

1. **Enable Squash and Merge:**
   - [ ] GitHub → Settings → General → Pull Requests
   - [ ] Enable "Allow squash merging"
   - [ ] Set default to "Default to PR title for squash merge commits"

2. **Set PR Title Conventions:**
   - [ ] Use conventional commit format for PR titles
   - [ ] Example: `feat: add new feature` or `fix: resolve bug`

3. **First Deployment:**
   - [ ] Merge first PR to main
   - [ ] CI/CD creates v1.0.0 automatically
   - [ ] Check GitHub Releases for v1.0.0

4. **Done!** Every future merge will auto-version and deploy 🚀

