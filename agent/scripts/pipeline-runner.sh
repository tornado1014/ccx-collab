#!/bin/bash
# Pipeline Runner (Mac/Linux)
# Executes pipeline modes:
# - full: validate → plan → split → implement → merge → verify → review → retrospect
# - implement-only: validate → plan → split → implement → merge
# Usage: ./pipeline-runner.sh --task <task.json> --work-id <work_id> [--results-dir <dir>] [--mode <full|implement-only>]
set -u
set -o pipefail

TASK=""
WORK_ID=""
RESULTS_DIR=""
MODE="full"

while [ $# -gt 0 ]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    --work-id) WORK_ID="$2"; shift 2 ;;
    --results-dir) RESULTS_DIR="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ -z "${TASK}" ]; then
  echo "ERROR: --task is required" >&2
  exit 1
fi

if [ -z "${WORK_ID}" ]; then
  WORK_ID=$(python3 -c "
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('$TASK').read_bytes()).hexdigest()[:12])
")
fi

if [ -z "${RESULTS_DIR}" ]; then
  RESULTS_DIR="agent/results"
fi

if [ "${MODE}" != "full" ] && [ "${MODE}" != "implement-only" ]; then
  echo "ERROR: invalid --mode '${MODE}'. Expected 'full' or 'implement-only'." >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ORCHESTRATE="python3 ${SCRIPT_DIR}/orchestrate.py"

if [ "${SIMULATE_AGENTS:-0}" = "1" ] || [ "${SIMULATE_AGENTS:-}" = "true" ]; then
  CLAUDE_WRAPPER="${CLAUDE_CODE_CMD:-}"
  CODEX_WRAPPER="${CODEX_CLI_CMD:-}"
else
  CLAUDE_WRAPPER="${CLAUDE_CODE_CMD:-${SCRIPT_DIR}/claude-wrapper.sh}"
  CODEX_WRAPPER="${CODEX_CLI_CMD:-${SCRIPT_DIR}/codex-wrapper.sh}"
fi

VALIDATION_PATH="${RESULTS_DIR}/validation_${WORK_ID}.json"
PLAN_PATH="${RESULTS_DIR}/plan_${WORK_ID}.json"
DISPATCH_PATH="${RESULTS_DIR}/dispatch_${WORK_ID}.json"
DISPATCH_MATRIX_PATH="${RESULTS_DIR}/dispatch_${WORK_ID}.matrix.json"
IMPLEMENT_PATH="${RESULTS_DIR}/implement_${WORK_ID}.json"
PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')"
[ "${PLATFORM}" = "darwin" ] && PLATFORM="macos"
VERIFY_PATH="${RESULTS_DIR}/verify_${WORK_ID}_${PLATFORM}.json"
REVIEW_PATH="${RESULTS_DIR}/review_${WORK_ID}.json"
RETROSPECT_PATH="${RESULTS_DIR}/retrospect_${WORK_ID}.json"

require_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "ERROR: Expected output not found: $path" >&2
    exit 1
  fi
}

require_json_file() {
  local path="$1"
  local required_fields="$2"
  require_file "$path"

  python3 - "$path" "$required_fields" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
required = [field.strip() for field in sys.argv[2].split(",") if field.strip()]

with path.open("r", encoding="utf-8") as f:
    payload = json.load(f)

if not isinstance(payload, dict):
    raise SystemExit(f"ERROR: {path} is not a JSON object")

missing = [field for field in required if field and field not in payload]
if missing:
    raise SystemExit(f"ERROR: {path} missing required fields: {', '.join(missing)}")
PY

  if [ $? -ne 0 ]; then
    echo "ERROR: Invalid JSON payload in $path" >&2
    exit 1
  fi
}

run_cmd() {
  local stage="$1"
  shift
  echo "[${stage}]"
  "$@"
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "FATAL: ${stage} failed with exit code ${rc}" >&2
    exit 1
  fi
}

echo "=== Pipeline Runner ==="
echo "Task: ${TASK}"
echo "Work ID: ${WORK_ID}"
echo "Mode: ${MODE}"
echo "Results: ${RESULTS_DIR}"
echo ""

echo "[1/7] Validating task..."
run_cmd "validate-task" ${ORCHESTRATE} validate-task --task "${TASK}" --work-id "${WORK_ID}" --out "${VALIDATION_PATH}"
require_json_file "${VALIDATION_PATH}" "status"

echo "[2/7] Planning (Claude)..."
run_cmd "plan" env CLAUDE_CODE_CMD="${CLAUDE_WRAPPER}" ${ORCHESTRATE} run-plan --task "${TASK}" --work-id "${WORK_ID}" --out "${PLAN_PATH}"
require_json_file "${PLAN_PATH}" "status"

echo "[3/7] Splitting task..."
run_cmd "split-task" ${ORCHESTRATE} split-task --task "${TASK}" --plan "${PLAN_PATH}" --out "${DISPATCH_PATH}" --matrix-output "${DISPATCH_MATRIX_PATH}"
require_json_file "${DISPATCH_PATH}" "subtasks"

echo "[4/7] Implementing subtasks (parallel)..."
SUBTASK_DATA=$(
python3 - "${DISPATCH_PATH}" <<'PY'
import json
import pathlib
import sys

dispatch = json.loads(pathlib.Path(sys.argv[1]).read_text())
for st in dispatch.get("subtasks", []):
    role = st.get("role", st.get("owner", "builder"))
    if role == "claude":
        role = "architect"
    elif role == "codex":
        role = "builder"
    print(f"{st['subtask_id']}|{role}")
PY
)

IMPL_PIDS=""
if [ -n "${SUBTASK_DATA}" ]; then
while IFS= read -r line; do
  IFS='|' read -r subtask_id role <<< "$line"
  [ -z "$subtask_id" ] && continue

  if [ "$role" = "architect" ]; then
    export CLAUDE_CODE_CMD="${CLAUDE_WRAPPER}"
    export CODEX_CLI_CMD=""
  else
    export CODEX_CLI_CMD="${CODEX_WRAPPER}"
    export CLAUDE_CODE_CMD=""
  fi

  echo "  -> ${subtask_id} (role=${role})"
  ${ORCHESTRATE} run-implement \
    --task "${TASK}" \
    --dispatch "${DISPATCH_PATH}" \
    --subtask-id "${subtask_id}" \
    --work-id "${WORK_ID}" \
    --out "${RESULTS_DIR}/implement_${WORK_ID}_${subtask_id}.json" \
    >/tmp/pipeline-implement-${WORK_ID}-${subtask_id}.log 2>&1 &
  IMPL_PIDS="${IMPL_PIDS} $!"
done <<< "${SUBTASK_DATA}"
fi

IMPL_FAIL=0
for pid in ${IMPL_PIDS}; do
  if ! wait "${pid}"; then
    IMPL_FAIL=$((IMPL_FAIL + 1))
  fi
done

if [ "${IMPL_FAIL}" -gt 0 ]; then
  echo "FATAL: ${IMPL_FAIL} implementation job(s) failed." >&2
  exit 1
fi

echo "[5/7] Merging results..."
run_cmd "merge-results" ${ORCHESTRATE} merge-results --work-id "${WORK_ID}" --kind implement --input "${RESULTS_DIR}/implement_${WORK_ID}_*.json" --dispatch "${DISPATCH_PATH}" --out "${IMPLEMENT_PATH}"
require_json_file "${IMPLEMENT_PATH}" "status"

if [ "${MODE}" = "implement-only" ]; then
  echo "[6/7] implement-only mode complete."
  echo ""
  echo "=== Pipeline Complete ==="
  echo "Implement: ${IMPLEMENT_PATH}"
  exit 0
fi

echo "[6/7] Verifying..."
run_cmd "verify" ${ORCHESTRATE} run-verify --work-id "${WORK_ID}" --platform "${PLATFORM}" --out "${VERIFY_PATH}"
require_json_file "${VERIFY_PATH}" "status"

echo "[7/7] Reviewing and generating retrospective..."
run_cmd "review" ${ORCHESTRATE} run-review --work-id "${WORK_ID}" --plan "${PLAN_PATH}" --implement "${IMPLEMENT_PATH}" --verify "${VERIFY_PATH}" --out "${REVIEW_PATH}"
require_json_file "${REVIEW_PATH}" "status,go_no_go"

run_cmd "retrospect" ${ORCHESTRATE} run-retrospect --work-id "${WORK_ID}" --review "${REVIEW_PATH}" --out "${RETROSPECT_PATH}"
require_json_file "${RETROSPECT_PATH}" "status"

echo ""
echo "=== Pipeline Complete ==="
echo "Review: ${REVIEW_PATH}"
echo "Retrospective: ${RETROSPECT_PATH}"
