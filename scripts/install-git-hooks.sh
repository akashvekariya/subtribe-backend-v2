#!/bin/bash
#
# Install Git hooks
# Copies pre-commit hook to .git/hooks/ directory
#

set -e

echo "📦 Installing Git hooks..."
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a Git repository root"
    echo "   Run this script from the project root directory"
    exit 1
fi

# Check if pre-commit hook exists
if [ ! -f "scripts/pre-commit" ]; then
    echo "❌ Error: scripts/pre-commit not found"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-commit hook
cp scripts/pre-commit .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit

echo "✅ Pre-commit hook installed successfully!"
echo ""
echo "What happens now:"
echo "  • Every time you run 'git commit', the hook will run automatically"
echo "  • It will check:"
echo "    1. Linting (ruff check)"
echo "    2. Code formatting (ruff format)"
echo "    3. Unit tests (pytest)"
echo "  • If any check fails, the commit will be blocked"
echo "  • Fix the issues and try committing again"
echo ""
echo "To bypass the hook (NOT recommended):"
echo "  git commit --no-verify"
echo ""
echo "To uninstall the hook:"
echo "  rm .git/hooks/pre-commit"
echo ""

