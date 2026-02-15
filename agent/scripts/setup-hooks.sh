#!/usr/bin/env bash
# setup-hooks.sh - Install and verify pre-commit hooks
# Usage: ./agent/scripts/setup-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=== Setting up pre-commit hooks ==="

# Check that pre-commit is installed
if ! command -v pre-commit &>/dev/null; then
    echo "ERROR: pre-commit is not installed."
    echo "Install it with: pip install pre-commit"
    exit 1
fi

# Check that jsonschema is available (needed by validate-schemas hook)
if ! python3 -c "import jsonschema" &>/dev/null; then
    echo "ERROR: jsonschema Python package is not installed."
    echo "Install it with: pip install jsonschema"
    exit 1
fi

# Install pre-commit hooks into .git/hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Run all hooks against all files as an initial check
echo ""
echo "Running pre-commit hooks on all files..."
pre-commit run --all-files

echo ""
echo "=== Pre-commit hooks installed and verified successfully ==="
echo "Hooks will now run automatically on every git commit."
