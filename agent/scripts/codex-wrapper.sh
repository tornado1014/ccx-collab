#!/bin/bash
# Codex CLI Wrapper (Mac/Linux)
# Reads JSON payload from stdin, runs Codex CLI, outputs JSON envelope to stdout.
set -o pipefail

STDERR_FILE=$(mktemp)
trap '_emit_envelope_on_error; rm -f "$STDERR_FILE"' EXIT

EXIT_CODE=0
RESULT=""

_emit_envelope_on_error() {
  if [ "$ENVELOPE_EMITTED" != "1" ]; then
    json_encode_str() {
      python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""'
    }
    local stderr_enc
    stderr_enc=$(cat "$STDERR_FILE" 2>/dev/null | json_encode_str)
    printf '{"status":"failed","exit_code":%d,"stdout":"","stderr":%s,"result":{}}' \
      "${EXIT_CODE:-1}" "$stderr_enc"
  fi
}

ENVELOPE_EMITTED=0

# Read JSON payload from stdin
PAYLOAD=$(cat)
REQUEST=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('request',''))" 2>/dev/null) || REQUEST=""

# Build structured prompt from payload context
PROMPT=$(echo "$PAYLOAD" | python3 -c "
import sys, json
try:
    p = json.load(sys.stdin)
    parts = []
    if p.get('phase'):
        parts.append(f\"[Phase: {p['phase']}]\")
    if p.get('task_id') or (p.get('task',{}) if isinstance(p.get('task'),dict) else {}).get('task_id'):
        tid = p.get('task_id') or p.get('task',{}).get('task_id','')
        parts.append(f\"[Task: {tid}]\")
    if isinstance(p.get('subtask'), dict):
        st = p['subtask']
        parts.append(f\"[Subtask: {st.get('subtask_id','')} - {st.get('title','')}\")
        if st.get('acceptance_criteria'):
            ac_list = st['acceptance_criteria']
            if isinstance(ac_list, list):
                ac_strs = []
                for ac in ac_list:
                    if isinstance(ac, dict):
                        ac_strs.append(ac.get('description', str(ac)))
                    else:
                        ac_strs.append(str(ac))
                parts.append('Acceptance Criteria: ' + '; '.join(ac_strs))
    req = p.get('request', '')
    if req:
        parts.append(req)
    print('\n'.join(parts) if parts else 'Process the provided task payload and return structured JSON results.')
except Exception:
    print(p.get('request', '') if 'p' in dir() else 'Process the provided task payload and return structured JSON results.')
" 2>/dev/null) || PROMPT="${REQUEST:-Process the provided task payload and return structured JSON results.}"

if [ -z "$PROMPT" ]; then
  PROMPT="Process the provided task payload and return structured JSON results."
fi

# Prevent nested Claude Code sessions
unset CLAUDECODE

# Run Codex CLI
RESULT=$(codex --approval-mode full-auto --quiet "$PROMPT" 2>"$STDERR_FILE")
EXIT_CODE=$?

# JSON-encode helper
json_encode() {
  if command -v jq &>/dev/null; then
    jq -Rs .
  else
    python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'
  fi
}

STDOUT_ENC=$(printf '%s' "$RESULT" | json_encode)
STDERR_ENC=$(cat "$STDERR_FILE" | json_encode)

# Try to parse structured result from CLI output
PARSED=$(printf '%s' "$RESULT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    json.dump(data, sys.stdout)
except:
    print('{}')
" 2>/dev/null) || PARSED="{}"

STATUS="passed"
if [ "$EXIT_CODE" -ne 0 ]; then
  STATUS="failed"
fi

ENVELOPE_EMITTED=1
printf '{"status":"%s","exit_code":%d,"stdout":%s,"stderr":%s,"result":%s}\n' \
  "$STATUS" "$EXIT_CODE" "$STDOUT_ENC" "$STDERR_ENC" "$PARSED"
