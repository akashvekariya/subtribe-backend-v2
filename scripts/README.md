# Git Hooks

Pre-commit hooks to prevent broken code from reaching GitHub Actions.

## Installation

Run once to install the hooks:

```bash
./scripts/install-git-hooks.sh
```

## What It Does

The pre-commit hook runs automatically before every `git commit`:

1. **Ruff Linting** - Checks for code errors
2. **Code Formatting** - Ensures consistent formatting
3. **Unit Tests** - Runs all unit tests

If any check fails, the commit is **blocked** until you fix it.

## Example

```bash
# Try to commit with linting errors
git add .
git commit -m "fix: something"

# Output:
# 🔍 Running pre-commit checks...
# 📝 Step 1/3: Running Ruff linter...
# ❌ Linting failed! Fix errors before committing.
#    Run: ruff check . --select E,F,W

# Fix the errors, then commit again
ruff check . --fix
git commit -m "fix: something"

# Output:
# ✅ All pre-commit checks passed!
# 💾 Proceeding with commit...
```

## Bypassing the Hook (Emergency Only)

If you absolutely need to commit without running checks:

```bash
git commit --no-verify -m "your message"
```

⚠️ **Not recommended!** This defeats the purpose and may break CI/CD.

## Uninstalling

```bash
rm .git/hooks/pre-commit
```

## Benefits

- ✅ Catch issues **before** they reach GitHub Actions
- ✅ Save time (no waiting for CI to fail)
- ✅ Keep main branch clean
- ✅ Enforce code quality standards
- ✅ Same checks as CI/CD pipeline

## Files

- `pre-commit` - The actual hook script
- `install-git-hooks.sh` - Installation script
- `README.md` - This file

