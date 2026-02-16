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

### cc-collab CLI (recommended)

```bash
# Install
pip install -e .

# Run full pipeline
cc-collab run --task <path> --work-id <id>

# Simulate (no real CLI calls)
cc-collab --simulate run --task <path>

# Verbose logging (DEBUG level)
cc-collab -v run --task <path>

# Individual stages
cc-collab validate --task <path> --out <path>
cc-collab plan --task <path> --out <path>
cc-collab implement --task <path> --dispatch <path> --subtask-id <id> --out <path>

# Utilities
cc-collab health                          # CLI tool health check
cc-collab health --json --continuous      # Scheduled monitoring (JSON output)
cc-collab status --work-id <id>           # Pipeline progress dashboard
cc-collab cleanup --retention-days 7      # Old results cleanup
cc-collab init --task-id <id> --title "X" # Task template generator
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
cc-collab run --task <path> --work-id <id> --resume

# Force re-run from a specific stage
cc-collab run --task <path> --work-id <id> --resume --force-stage verify
```

## Configuration

Supports `.cc-collab.yaml` (project) and `~/.cc-collab/config.yaml` (user).
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

Hooks: ruff lint/format (`agent/` + `cc_collab/`), check-json, validate-schemas, check-yaml.
Skip in emergencies: `git commit --no-verify` (then run `pre-commit run --all-files`).

### Testing

```bash
python3 -m pytest tests/test_cc_collab/ agent/tests/ -v  # 426 tests
```

## Docker

```bash
docker build -t cc-collab .
docker run --rm cc-collab run --task /app/agent/tasks/example.task.json
docker compose run cc-collab --help
```

## Integration with Sisyphus

The pipeline can be triggered via the `/pipeline` keyword in Claude Code hooks.
Ultrawork mode and Ralph Loop are compatible with pipeline execution.
