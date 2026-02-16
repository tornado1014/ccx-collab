**English** | [한국어](README.ko.md)

# Agent Orchestration API Reference

A detailed API reference for the orchestration engine where Claude Code CLI (architect) and Codex CLI (builder) collaborate to execute automated development pipelines.

> For a full system overview and quick start guide, see the [root README.md](../README.md).

---

## Table of Contents

1. [API Reference](#api-reference)
   - [validate-task](#1-validate-task)
   - [run-plan](#2-run-plan)
   - [split-task](#3-split-task)
   - [run-implement](#4-run-implement)
   - [merge-results](#5-merge-results)
   - [run-verify](#6-run-verify)
   - [run-review](#7-run-review)
   - [run-retrospect](#8-run-retrospect)
2. [Schema Reference](#schema-reference)
3. [Troubleshooting Guide](#troubleshooting-guide)
4. [Configuration Reference](#configuration-reference)

---

## API Reference

All actions are executed as subcommands of `orchestrate.py`.

```bash
python3 agent/scripts/orchestrate.py [--verbose] <action> [options]
```

Global options:

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Enable DEBUG level logging |

### Exit Code Convention

| Exit Code | Meaning |
|-----------|---------|
| `0` | Success |
| `1` | Input error (file not found, JSON parsing failure, missing required parameters) |
| `2` | Logic failure (validation error, CLI failure, quality gate not passed) |

---

### 1. validate-task

Validates a task JSON file. Performs schema validation against `task.schema.json` and normalizes required fields.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--task` | Yes | - | Path to the task JSON file |
| `--work-id` | No | `""` | Work identifier (uses task_id if not specified) |
| `--out` | No | `agent/results/validation_{task_id}.json` | Output path for results |

#### Output Format

```json
{
  "agent": "validation",
  "work_id": "my-task-001",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready",
  "validation_errors": [],
  "task": { "...normalized task object..." }
}
```

`status` values:
- `"ready"` -- Validation passed, pipeline can proceed
- `"blocked"` -- validation_errors present, corrections required

#### Normalization Behavior

- If `task_id` is missing, `"task-unknown"` is automatically assigned
- If `subtasks` is a string array, it is converted to object format
- The `platform` value is normalized to the range `["mac", "windows", "both"]`
- If `subtask_id` is not specified, it is auto-generated using the pattern `{task_id}-S{01,02,...}`

#### Usage Example

```bash
python3 agent/scripts/orchestrate.py validate-task \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/validation_demo.json
```

---

### 2. run-plan

Invokes the Claude Code CLI to create a plan that decomposes the task into 30-90 minute implementation chunks.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--task` | Yes | - | Path to the task JSON file |
| `--work-id` | No | task_id | Work identifier |
| `--out` | Yes | - | Output path for the plan result |

#### Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_CODE_CMD` | Claude CLI execution command (requires `SIMULATE_AGENTS=1` if not set) |
| `SIMULATE_AGENTS` | When set to `1`, runs simulation without CLI invocation |

#### Output Format

```json
{
  "agent": "claude",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "implementation_contract": ["criterion 1", "criterion 2"],
  "test_plan": ["pytest -v", "flake8"],
  "open_questions": [],
  "chunks": [
    {
      "chunk_id": "demo-C01",
      "title": "Add orchestrator schemas",
      "estimated_minutes": 60,
      "role": "builder",
      "depends_on": [],
      "scope": "implementation",
      "files_affected": ["agent/schemas/*.json"],
      "acceptance_criteria": [
        {
          "id": "AC-S01-1",
          "description": "Schema files are valid JSON",
          "verify_command": "python3 -c \"import json...\"",
          "verify_pattern": "",
          "category": "functional"
        }
      ],
      "source_subtask_id": "demo-S01"
    }
  ],
  "machine_readable_criteria": [],
  "cli_output": { "...raw CLI response..." }
}
```

`status` values:
- `"done"` -- Planning completed successfully
- `"blocked"` -- CLI failed or result could not be parsed

#### Chunk Splitting Logic

1. If the CLI returns a structured `chunks` array, it is used as-is
2. Otherwise, chunks are auto-generated from the task's subtasks:
   - `estimated_minutes <= 90`: Single chunk
   - `estimated_minutes > 90`: Automatically split into 90-minute units (acceptance_criteria are distributed accordingly)
   - Clamped to a minimum of 30 minutes and a maximum of 90 minutes

#### Usage Example

```bash
# Simulation mode
SIMULATE_AGENTS=1 python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json

# Live CLI integration
CLAUDE_CODE_CMD="claude --print" python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json
```

---

### 3. split-task

Generates per-subtask dispatch files based on the plan result. Assigns a `role` (architect/builder) and `owner` (claude/codex) to each subtask.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--task` | Yes | - | Path to the task JSON file |
| `--plan` | No | `""` | Path to the run-plan result file (uses only task subtasks if not specified) |
| `--out` | Yes | - | Output path for the dispatch result |
| `--matrix-output` | No | `""` | Output path for a CI matrix JSON (compact subtask list) |

#### Output Format (dispatch)

```json
{
  "agent": "dispatch",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "plan_version": "v1",
  "subtasks": [
    {
      "subtask_id": "demo-S01",
      "title": "Add orchestrator schemas and scripts",
      "role": "builder",
      "owner": "codex",
      "scope": "implementation",
      "estimated_minutes": 60,
      "depends_on": [],
      "files_affected": ["agent/schemas/*.json"],
      "acceptance_criteria": [],
      "notes": [],
      "work_id": "demo",
      "risk_level": "medium",
      "source_subtask_id": null
    }
  ],
  "dispatch_from_plan": {
    "implementation_contract": [],
    "test_plan": []
  }
}
```

#### Matrix Output Format

When `--matrix-output` is specified, a compact array suitable for CI parallel job dispatch is written:

```json
[
  {
    "subtask_id": "demo-S01",
    "role": "builder",
    "owner": "codex",
    "estimated_minutes": 60,
    "depends_on": []
  }
]
```

#### Role Determination Priority

1. If `subtask.role` is `"architect"` or `"builder"`, it is used as-is
2. `subtask.owner == "claude"` -> `architect`
3. `subtask.owner == "codex"` -> `builder`
4. Default: `builder`

#### Usage Example

```bash
python3 agent/scripts/orchestrate.py split-task \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json \
  --matrix-output agent/results/dispatch_demo.matrix.json
```

---

### 4. run-implement

Executes an individual dispatched subtask using the CLI agent assigned to the corresponding role (Claude or Codex).

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--task` | Yes | - | Path to the task JSON file |
| `--dispatch` | No | `""` | Path to the dispatch file (split-task result) |
| `--subtask-id` | Yes | - | ID of the subtask to execute |
| `--work-id` | No | task_id | Work identifier |
| `--out` | Yes | - | Output path for results |

#### Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_CODE_CMD` | Used for executing architect role subtasks |
| `CODEX_CLI_CMD` | Used for executing builder role subtasks |
| `SIMULATE_AGENTS` | When set to `1`, enables simulation mode |
| `AGENT_MAX_RETRIES` | Maximum CLI call retry count (default: `2`) |
| `AGENT_RETRY_SLEEP` | Retry wait time in seconds (default: `20`) |
| `CLI_TIMEOUT_SECONDS` | CLI command timeout in seconds (default: `300`) |

#### Output Format

```json
{
  "agent": "codex",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "subtask": { "...subtask object..." },
  "role": "builder",
  "files_changed": ["agent/schemas/task.schema.json"],
  "commands_executed": [
    {
      "status": "passed",
      "command": "codex --approval-mode full-auto --quiet",
      "return_code": 0,
      "stdout": "...",
      "stderr": ""
    }
  ],
  "failed_tests": [],
  "artifacts": [],
  "cli_output": { "...raw CLI response..." },
  "open_questions": []
}
```

`status` values:
- `"done"` -- Implementation succeeded
- `"failed"` -- CLI terminated abnormally
- `"blocked"` -- CLI output could not be parsed (non-simulation mode)

#### Subtask Lookup Order

1. Match `subtask_id` in the `subtasks` array of the `--dispatch` file
2. If not found, match `subtask_id` in the `subtasks` array of the `--task` file
3. If neither matches, an error is raised (listing available subtask IDs)

#### Usage Example

```bash
# Simulation mode
SIMULATE_AGENTS=1 python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id ci-cd-collab-baseline-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json

# Live CLI (builder role -> uses CODEX_CLI_CMD)
CODEX_CLI_CMD="codex --approval-mode full-auto --quiet" \
  python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id ci-cd-collab-baseline-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json
```

---

### 5. merge-results

Merges multiple subtask implementation results into a single consolidated report. Uses file locking to prevent concurrent access.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--work-id` | Yes | - | Work identifier |
| `--kind` | Yes | - | Result kind (e.g., `implement`) |
| `--input` | Yes | - | Input file path (supports glob patterns, e.g., `results/implement_demo_*.json`) |
| `--out` | Yes | - | Output path for the merged result |
| `--dispatch` | No | `""` | Path to the dispatch file (used for detecting unexecuted subtasks) |

#### Output Format

```json
{
  "agent": "implement",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "count": 2,
  "subtask_results": [ "...individual subtask results..." ],
  "files_changed": ["file1.py", "file2.json"],
  "commands_executed": [],
  "failed_tests": [],
  "artifacts": [],
  "open_questions": [],
  "expected_subtasks": ["demo-S01", "demo-S02"],
  "missing_subtasks": []
}
```

`status` determination logic (`build_report_status`):

| Status found in sub-results | Final status |
|-----------------------------|--------------|
| `"failed"` or `"skipped"` | `"failed"` |
| `"blocked"` | `"blocked"` |
| `"simulated"` | `"done"` |
| `"passed"` | `"done"` |
| `"ready"` | `"ready"` |

> `"skipped"` is treated identically to `"failed"`. This is an intentional quality policy.

#### File Lock Mechanism

- Creates a lock file with the `.lock` extension for the output file
- macOS/Linux: `fcntl.flock` (LOCK_EX | LOCK_NB)
- Windows: `msvcrt.locking` (LK_NBLCK)
- Uses non-blocking mode; returns an error immediately if the file is already locked

#### Dispatch-Based Completeness Check

When `--dispatch` is specified, the system verifies that all `subtask_id` values from the dispatch file's `subtasks` are present in the results. If any subtasks are missing, the status is changed to `"failed"`.

#### Usage Example

```bash
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo \
  --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --dispatch agent/results/dispatch_demo.json \
  --out agent/results/implement_demo.json
```

---

### 6. run-verify

Executes configured verification commands (tests, linting, etc.) and generates a JUnit XML report.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--work-id` | Yes | - | Work identifier |
| `--platform` | Yes | - | Execution platform (e.g., `macos`, `windows`) |
| `--out` | Yes | - | Output path for verification results |
| `--commands` | No | `""` | Verification commands (overrides all other sources when specified directly) |

#### Verification Command Sources (in priority order)

1. `--commands` parameter (directly specified)
2. `VERIFY_COMMANDS` environment variable
3. `default_verify_commands` array in `pipeline-config.json`
4. If none of the above are available, the **pipeline fails** (status: `"failed"`)

#### VERIFY_COMMANDS Format

```bash
# JSON array (recommended)
export VERIFY_COMMANDS='["pytest -v", "flake8"]'

# Semicolon-separated
export VERIFY_COMMANDS="pytest -v; flake8"

# Newline-separated
export VERIFY_COMMANDS="pytest -v
flake8"
```

#### Output Format

```json
{
  "agent": "verify",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "platform": "macos",
  "status": "passed",
  "commands": [
    {
      "command": "python3 -m pytest agent/tests/ -v --tb=short",
      "status": "passed",
      "return_code": 0,
      "time_ms": 3200,
      "stdout": "...test output (max 6000 chars)...",
      "stderr": "...(max 3000 chars)..."
    }
  ],
  "failed_tests": [],
  "artifacts": ["agent/results/junit_demo_macos.xml"],
  "open_questions": []
}
```

#### JUnit XML Report

A `junit_{work_id}_{platform}.xml` file is automatically generated in the output directory during verification. It can be integrated with CI system test report features.

#### Usage Example

```bash
# Using environment variables
VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]' \
  python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo \
  --platform macos \
  --out agent/results/verify_demo_macos.json

# Specifying commands directly
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo \
  --platform macos \
  --commands '["pytest -v", "flake8"]' \
  --out agent/results/verify_demo_macos.json
```

---

### 7. run-review

A quality gate that aggregates Plan, Implement, and Verify results to make a go/no-go determination.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--work-id` | Yes | - | Work identifier |
| `--plan` | Yes | - | Path to the run-plan result file |
| `--implement` | Yes | - | Path to the merge-results result file |
| `--verify` | No | `[]` | Path(s) to run-verify result file(s) (accepts multiple, nargs) |
| `--out` | Yes | - | Output path for the review result |

#### Go/No-Go Criteria

**All conditions must be met for `go_no_go = false` (pass):**

| Condition | Expected Value |
|-----------|----------------|
| Plan status | `"done"` |
| Implementation status | `"done"` |
| All Verify statuses | `"passed"` |
| open_questions across all stages | 0 |

> `go_no_go` is a boolean where `true` means "blocked" and `false` means "passed (ready to merge)".

#### Output Format

```json
{
  "agent": "review",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready_for_merge",
  "claude_review": {
    "status": "approved",
    "notes": []
  },
  "codex_review": {
    "status": "implemented",
    "notes": []
  },
  "action_required": [],
  "open_questions": [],
  "go_no_go": false,
  "references": {
    "plan": "agent/results/plan_demo.json",
    "implement": "agent/results/implement_demo.json",
    "verify": ["macos"]
  }
}
```

`status` values:
- `"ready_for_merge"` -- All quality gates passed
- `"blocked"` -- One or more gates did not pass

#### Usage Example

```bash
python3 agent/scripts/orchestrate.py run-review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo_macos.json agent/results/verify_demo_windows.json \
  --out agent/results/review_demo.json
```

---

### 8. run-retrospect

Analyzes the review result and generates an improvement plan (next_plan) for the next cycle.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--work-id` | Yes | - | Work identifier |
| `--review` | Yes | - | Path to the run-review result file |
| `--out` | Yes | - | Output path for the retrospective result |

#### Output Format

```json
{
  "agent": "retrospect",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready",
  "summary": {
    "go_no_go": false,
    "issues_count": 0,
    "next_action_count": 1
  },
  "next_plan": [
    {
      "index": 1,
      "type": "observe",
      "title": "No critical issues; run routine quality tuning on next cycle.",
      "owner": "both",
      "priority": "medium"
    }
  ],
  "evidence": {
    "review_reference": "agent/results/review_demo.json",
    "questions": []
  }
}
```

#### Next Plan Generation Logic

1. If `action_required` items exist, a `type: "rework"` action is created for each (up to 5)
   - If the item contains `"implementation"` -> `owner: "codex"`
   - Otherwise -> `owner: "claude"`
   - All are assigned `priority: "high"`
2. If both `action_required` and `open_questions` are empty, a single `type: "observe"` item is generated

#### Usage Example

```bash
python3 agent/scripts/orchestrate.py run-retrospect \
  --work-id demo \
  --review agent/results/review_demo.json \
  --out agent/results/retrospect_demo.json
```

---

## Schema Reference

All schemas are located in the `agent/schemas/` directory. When the `jsonschema` package is installed, schema validation is automatically performed during validate-task.

| Schema File | Purpose | Required Fields |
|-------------|---------|-----------------|
| `task.schema.json` | Input task definition | `task_id`, `title`, `scope`, `acceptance_criteria`, `risk_level`, `priority`, `subtasks` |
| `cli-envelope.schema.json` | CLI agent stdout output wrapper | `status`, `exit_code`, `stdout`, `stderr` |
| `plan-result.schema.json` | run-plan result | `status`, `implementation_contract`, `test_plan`, `open_questions` |
| `implement-result.schema.json` | run-implement result | `status`, `files_changed`, `commands_executed`, `failed_tests`, `artifacts` |
| `review-result.schema.json` | run-review result | `claude_review`, `codex_review`, `action_required`, `go_no_go` |
| `retrospect.schema.json` | run-retrospect result | `status`, `summary`, `next_plan`, `evidence` |

### task.schema.json Details

Defines the structure of task input files. `acceptance_criteria` supports two formats:

```json
// String format (simple)
"acceptance_criteria": ["Tests pass", "Lint clean"]

// Object format (machine-verifiable)
"acceptance_criteria": [
  {
    "id": "AC-S01-1",
    "description": "Schema files are valid JSON",
    "verification": "python3 -c \"import json...\"",
    "type": "automated"
  }
]
```

The subtask `role` field accepts either `"architect"` or `"builder"`. For backward compatibility, the `owner: "claude"/"codex"` field is also supported.

### cli-envelope.schema.json Details

The JSON envelope output to stdout by CLI wrappers (claude-wrapper.sh, codex-wrapper.sh). Uses `additionalProperties: false` to disallow fields outside the schema.

```json
{
  "status": "passed",
  "exit_code": 0,
  "stdout": "{\"result\": {\"files_changed\": [\"app.py\"]}}",
  "stderr": "",
  "result": { "files_changed": ["app.py"] }
}
```

### plan-result.schema.json Details

Each item in the `chunks` array represents a 30-90 minute implementation unit and includes machine-verifiable acceptance_criteria:

```json
{
  "chunk_id": "task-C01",
  "title": "Setup project structure",
  "estimated_minutes": 60,
  "role": "builder",
  "depends_on": [],
  "acceptance_criteria": [
    {
      "id": "AC-001",
      "description": "Project directories exist",
      "verify_command": "test -d src && test -d tests",
      "verify_pattern": "",
      "category": "structural"
    }
  ]
}
```

`category` values: `"functional"`, `"structural"`, `"quality"`, `"integration"`

---

## Troubleshooting Guide

### "CLI command not configured"

**Symptom**: `RuntimeError: claude CLI command not configured` or `codex CLI command not configured`

**Cause**: `CLAUDE_CODE_CMD` or `CODEX_CLI_CMD` environment variable is not set, and `SIMULATE_AGENTS` is also inactive.

**Solution**:

```bash
# Option 1: Set CLI paths
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"

# Option 2: Use simulation mode (test without CLI)
export SIMULATE_AGENTS=1
```

---

### "Task validation failed"

**Symptom**: validate-task returns exit code 2 with an error list in `validation_errors`.

**Cause**: The task JSON does not satisfy the required fields or format constraints of `task.schema.json`.

**Solution**:

```bash
# 1. Check validation results
python3 agent/scripts/orchestrate.py validate-task \
  --task your_task.json \
  --out /tmp/validation.json --verbose

# 2. Inspect errors in the result file
python3 -c "import json; print(json.dumps(json.load(open('/tmp/validation.json'))['validation_errors'], indent=2))"

# 3. Verify JSON syntax
python3 -m json.tool your_task.json
```

**Common errors**:

| validation_error message | Cause | Fix |
|--------------------------|-------|-----|
| `missing task_id` | task_id field is missing | Add `"task_id": "my-task-001"` |
| `missing title` | title field is empty | Provide a meaningful title |
| `acceptance_criteria must be a non-empty array` | acceptance_criteria is missing or empty | Add at least one item |
| `subtasks should be an array` | subtasks is an object instead of an array | Convert to `[...]` array format |
| `jsonschema package not installed` | jsonschema is not installed | `pip install jsonschema` |

---

### "Verification skipped"

**Symptom**: run-verify returns exit code 1 with `status: "failed"`, and `open_questions` contains the message "VERIFY_COMMANDS not configured".

**Cause**: No verification commands are configured from any source.

**Solution**:

```bash
# Option 1: Set environment variable (recommended)
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v", "flake8"]'

# Option 2: Specify commands directly
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo --platform macos \
  --commands '["pytest -v"]' \
  --out agent/results/verify_demo.json

# Option 3: Set defaults in pipeline-config.json
# "default_verify_commands": ["pytest -v", "flake8"]
```

> Per the pipeline quality policy, an unconfigured `VERIFY_COMMANDS` results in immediate failure. There is no "skipped" status; if verification cannot be performed, the result is always `"failed"`.

---

### "Merge lock failed"

**Symptom**: merge-results returns exit code 1 with the error `Unable to acquire merge lock`.

**Cause**: Another pipeline process is writing to the same output file, or a stale lock file from a previous run remains.

**Solution**:

```bash
# 1. Check for other processes
ps aux | grep orchestrate

# 2. Check for and remove stale lock files
ls -la agent/results/*.lock
rm agent/results/implement_demo.json.lock  # remove stale lock

# 3. Re-run
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --out agent/results/implement_demo.json
```

---

### "Command timed out"

**Symptom**: `Command timed out after Ns` error. A CLI command or verification command exceeded the timeout duration.

**Cause**: The command's execution time exceeds CLI_TIMEOUT_SECONDS (default: 300 seconds).

**Solution**:

```bash
# Increase timeout (in seconds)
export CLI_TIMEOUT_SECONDS=600  # 10 minutes

# If only specific commands need timeout adjustment,
# add timeout options to the verification commands themselves
export VERIFY_COMMANDS='["timeout 120 pytest -v --timeout=60"]'
```

---

### "Rate limit exceeded"

**Symptom**: The CLI agent returns a rate limit error and fails even after retries.

**Cause**: The Claude or Codex API call frequency limit has been reached.

**Solution**:

```bash
# Increase retry count
export AGENT_MAX_RETRIES=5

# Increase retry wait time (in seconds)
export AGENT_RETRY_SLEEP=60

# Change defaults in pipeline-config.json
# "defaults": { "rate_limit_seconds": 5, "retry_count": 3 }
```

> `run_agent_command` retries up to `AGENT_MAX_RETRIES` times on failure, waiting `AGENT_RETRY_SLEEP` seconds between each retry. On success (`return_code == 0`), it returns immediately.

---

### Additional Tips

| Situation | Diagnostic Approach |
|-----------|---------------------|
| Unsure which stage is failing | Add the `--verbose` option to view DEBUG logs |
| Want to inspect raw CLI output | Check the `cli_output` field in the result JSON |
| Testing the full pipeline | `SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh --task ... --work-id test` |
| Unknown subtask IDs | Check `subtasks[].subtask_id` in validate-task or split-task results |
| Resuming pipeline from a midpoint | Invoke the specific action directly, specifying paths to previous stage results |

---

## Configuration Reference

### pipeline-config.json

The central configuration file that controls pipeline behavior. Location: `agent/pipeline-config.json`

```json
{
  "pipeline_mode": "local-only",
  "supported_modes": ["local-only", "orchestrator-centralized"],
  "defaults": { ... },
  "roles": { ... },
  "default_verify_commands": [ ... ]
}
```

#### Full Option List

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pipeline_mode` | string | `"local-only"` | Pipeline execution mode. `"local-only"`: single-machine execution, `"orchestrator-centralized"`: uses a central orchestrator |
| `supported_modes` | string[] | `["local-only", "orchestrator-centralized"]` | List of supported execution modes |

#### defaults Section

| Key | Type | Default | Env Variable Override | Description |
|-----|------|---------|-----------------------|-------------|
| `max_retries` | int | `2` | `AGENT_MAX_RETRIES` | Maximum CLI call retry count |
| `retry_sleep_seconds` | int | `20` | `AGENT_RETRY_SLEEP` | Wait time between retries (seconds) |
| `cli_timeout_seconds` | int | `300` | `CLI_TIMEOUT_SECONDS` | CLI command timeout (seconds) |
| `rate_limit_seconds` | int | `2` | `AGENT_RATE_LIMIT` | Minimum interval between API calls (seconds) |
| `retry_count` | int | `2` | - | Alias for max_retries |
| `log_level` | string | `"INFO"` | - | Logging level (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`) |
| `result_retention_days` | int | `30` | - | Result file retention period (days) |
| `results_dir_pattern` | string | `"agent/results/{os_prefix}/{work_id}"` | - | Result directory path pattern |

#### roles Section

| Role | Description | Environment Variable |
|------|-------------|----------------------|
| `architect` | Planning, design, review -- primarily Claude Code CLI | `CLAUDE_CODE_CMD` |
| `builder` | Implementation, execution, testing -- primarily Codex CLI | `CODEX_CLI_CMD` |

#### default_verify_commands

The default verification command array used when the VERIFY_COMMANDS environment variable is not set:

```json
"default_verify_commands": [
  "python3 -m pytest agent/tests/ -v --tb=short",
  "python3 -c \"import json,pathlib; [json.loads(p.read_text()) for p in pathlib.Path('agent/schemas').glob('*.json')]\""
]
```

### Full Environment Variable List

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLAUDE_CODE_CMD` | Conditional* | - | Claude Code CLI execution command |
| `CODEX_CLI_CMD` | Conditional* | - | Codex CLI execution command |
| `SIMULATE_AGENTS` | No | `"0"` | Enables simulation mode when set to `"1"` or `"true"` |
| `VERIFY_COMMANDS` | No | See pipeline-config.json | Verification commands (supports JSON array, semicolon, or newline delimiters) |
| `AGENT_MAX_RETRIES` | No | `"2"` | Maximum CLI call retry count |
| `AGENT_RETRY_SLEEP` | No | `"20"` | Retry wait time (seconds) |
| `CLI_TIMEOUT_SECONDS` | No | `"300"` | CLI command timeout (seconds) |

> *When `SIMULATE_AGENTS=1` is not set, `CLAUDE_CODE_CMD` is required for architect subtask execution and `CODEX_CLI_CMD` is required for builder subtask execution.

### pipeline-runner.sh Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--task` | Yes | - | Path to the task JSON file |
| `--work-id` | No | SHA256(task file)[:12] | Work identifier (auto-generated from task file hash if not specified) |
| `--results-dir` | No | `agent/results` | Results output directory |
| `--mode` | No | `full` | Execution mode: `full` (all 8 stages) or `implement-only` (validate through merge, 5 stages only) |
