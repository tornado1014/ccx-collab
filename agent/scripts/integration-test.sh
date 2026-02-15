#!/bin/bash
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Unset CLAUDECODE for nested session safety
unset CLAUDECODE

TASK="agent/tasks/example.task.json"
WORK_ID="integration-$(date +%s)"
RESULTS_DIR="agent/results/integration"

# Auto-detect: use simulation if CLI tools not found
if [ -z "${SIMULATE_AGENTS:-}" ]; then
  if command -v claude &>/dev/null; then
    SIMULATE_AGENTS=0
  else
    SIMULATE_AGENTS=1
    echo "CLI tools not found, using simulation mode"
  fi
fi

export SIMULATE_AGENTS

# Set default VERIFY_COMMANDS if not set
if [ -z "${VERIFY_COMMANDS:-}" ]; then
  export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v --tb=short"]'
fi

./agent/scripts/pipeline-runner.sh \
  --task "${TASK}" \
  --work-id "${WORK_ID}" \
  --results-dir "${RESULTS_DIR}" \
  --mode full

echo ""
echo "Integration test Complete"
