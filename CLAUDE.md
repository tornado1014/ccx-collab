# Claude Code + Codex CLI Collaboration System

## Project Overview

CI/CD collaboration system where Claude Code CLI and Codex CLI work together within each OS (Mac/Windows) to perform automated development cycles.

## Pipeline Participation

When participating in a pipeline task:
1. Read the task JSON from stdin
2. Return structured JSON results
3. Envelope format: see `agent/schemas/cli-envelope.schema.json`

### Schema Versioning

All schemas enforce version `1.0.0` (backward-compatible, optional field with default):
- `task.schema.json`, `cli-envelope.schema.json`, `plan-result.schema.json`
- `implement-result.schema.json`, `review-result.schema.json`, `retrospect.schema.json`

## Key Commands

### ccx-collab CLI (recommended)

```bash
# Install
pip install -e .

# Run full pipeline
ccx-collab run --task <path> --work-id <id>

# Simulate (no real CLI calls)
ccx-collab --simulate run --task <path>

# Verbose logging (DEBUG level)
ccx-collab -v run --task <path>

# Individual stages
ccx-collab validate --task <path> --out <path>
ccx-collab plan --task <path> --out <path>
ccx-collab implement --task <path> --dispatch <path> --subtask-id <id> --out <path>

# Utilities
ccx-collab health                          # CLI tool health check
ccx-collab health --json --continuous      # Scheduled monitoring (JSON output)
ccx-collab status --work-id <id>           # Pipeline progress dashboard
ccx-collab cleanup --retention-days 7      # Old results cleanup
ccx-collab init --task-id <id> --title "X" # Task template generator
```

### Legacy commands (still supported)

```bash
python3 agent/scripts/orchestrate.py validate-task --task <path> --work-id <id> --out <path>
./agent/scripts/pipeline-runner.sh --task <path> --work-id <id>
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh --task <path> --work-id <id>
```

## Resume & Checkpoint

The pipeline supports resuming from the last successful stage:

```bash
# Resume from where it left off
ccx-collab run --task <path> --work-id <id> --resume

# Force re-run from a specific stage
ccx-collab run --task <path> --work-id <id> --resume --force-stage verify
```

## Configuration

Supports `.ccx-collab.yaml` (project) and `~/.ccx-collab/config.yaml` (user).
Precedence: CLI flags > project config > user config > built-in defaults.

## Quality Policies

- `skipped` verification = pipeline failure
- `VERIFY_COMMANDS` must be configured
- Only `status: "passed"` passes the review gate
- Role-based execution: `architect` (Claude) / `builder` (Codex)

## Development Workflow

### Pre-commit Hooks

```bash
pip install pre-commit && pre-commit install
```

Hooks: ruff lint/format (`agent/` + `ccx_collab/`), check-json, validate-schemas, check-yaml.
Skip in emergencies: `git commit --no-verify` (then run `pre-commit run --all-files`).

### Testing

```bash
python3 -m pytest tests/test_ccx_collab/ agent/tests/ -v  # 541 tests
```

## Docker

```bash
docker build -t ccx-collab .
docker run --rm ccx-collab run --task /app/agent/tasks/example.task.json
docker compose run ccx-collab --help
```

## Web Dashboard

```bash
# Install with web dependencies
pip install -e ".[web]"

# Start dashboard (default: http://localhost:8000)
ccx-collab web
ccx-collab web --port 9000 --reload  # custom port + auto-reload
```

Features: pipeline monitoring (SSE), task management (CRUD), run history with charts,
webhook settings + delivery logs, Mermaid pipeline visualization, i18n (en/ko),
individual stage execution, health check, cleanup manager, config editor,
log viewer (SSE streaming), result file browser, resume/force-stage pipeline control.

Stack: FastAPI + HTMX + Tailwind CSS v4 + Alpine.js + SQLite (aiosqlite).

## Integration with Sisyphus

The pipeline can be triggered via the `/pipeline` keyword in Claude Code hooks.
Ultrawork mode and Ralph Loop are compatible with pipeline execution.
