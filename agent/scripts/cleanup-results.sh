#!/usr/bin/env bash
# Cleanup Results Script (Mac/Linux)
# Removes old JSON result files from the results directory.
# Usage: ./cleanup-results.sh [--results-dir <dir>] [--retention-days <n>] [--dry-run]
set -euo pipefail

RESULTS_DIR="agent/results"
RETENTION_DAYS=30
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --results-dir) RESULTS_DIR="$2"; shift 2 ;;
    --retention-days) RETENTION_DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ ! -d "${RESULTS_DIR}" ]; then
  echo "ERROR: Results directory does not exist: ${RESULTS_DIR}" >&2
  exit 1
fi

# Validate retention days is a positive integer
if ! echo "${RETENTION_DAYS}" | grep -qE '^[0-9]+$' || [ "${RETENTION_DAYS}" -lt 1 ]; then
  echo "ERROR: --retention-days must be a positive integer, got: ${RETENTION_DAYS}" >&2
  exit 1
fi

echo "=== Results Cleanup ==="
echo "Directory:      ${RESULTS_DIR}"
echo "Retention days: ${RETENTION_DAYS}"
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "Mode:           DRY RUN (no files will be deleted)"
else
  echo "Mode:           LIVE"
fi
echo ""

# Find JSON files older than retention days (only files, never directories)
DELETED_COUNT=0
FREED_BYTES=0

while IFS= read -r file; do
  [ -z "${file}" ] && continue

  # Get file size before potential deletion
  if [ "$(uname -s)" = "Darwin" ]; then
    FILE_SIZE=$(stat -f%z "${file}" 2>/dev/null || echo 0)
  else
    FILE_SIZE=$(stat --printf="%s" "${file}" 2>/dev/null || echo 0)
  fi

  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "[dry-run] Would delete: ${file} (${FILE_SIZE} bytes)"
  else
    rm -f "${file}"
    echo "Deleted: ${file}"
  fi

  DELETED_COUNT=$((DELETED_COUNT + 1))
  FREED_BYTES=$((FREED_BYTES + FILE_SIZE))
done < <(find "${RESULTS_DIR}" -maxdepth 1 -type f -name "*.json" -mtime "+${RETENTION_DAYS}" 2>/dev/null)

# Format freed space for human readability
FREED_DISPLAY=$(python3 -c "
b = ${FREED_BYTES}
if b >= 1048576:
    print(f'{b/1048576:.2f} MB')
elif b >= 1024:
    print(f'{b/1024:.2f} KB')
else:
    print(f'{b} bytes')
" 2>/dev/null || echo "${FREED_BYTES} bytes")

echo ""
echo "=== Summary ==="
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "Files that would be deleted: ${DELETED_COUNT}"
  echo "Space that would be freed:   ${FREED_DISPLAY}"
else
  echo "Files deleted: ${DELETED_COUNT}"
  echo "Space freed:   ${FREED_DISPLAY}"
fi
