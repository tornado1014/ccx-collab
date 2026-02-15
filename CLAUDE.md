# Claude Code + Codex CLI Collaboration System

## Project Overview

CI/CD collaboration system where Claude Code CLI and Codex CLI work together within each OS (Mac/Windows) to perform automated development cycles.

## Pipeline Participation

When participating in a pipeline task:
1. Read the task JSON from stdin
2. Return structured JSON results
3. Envelope format: see `agent/schemas/cli-envelope.schema.json`

## Key Commands

```bash
# Validate a task
python3 agent/scripts/orchestrate.py validate-task --task <path> --work-id <id> --out <path>

# Run full pipeline
./agent/scripts/pipeline-runner.sh --task <path> --work-id <id>

# Simulate (no real CLI calls)
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh --task <path> --work-id <id>
```

## Quality Policies

- `skipped` verification = pipeline failure
- `VERIFY_COMMANDS` must be configured
- Only `status: "passed"` passes the review gate
- Role-based execution: `architect` (Claude) / `builder` (Codex)

## Integration with Sisyphus

The pipeline can be triggered via the `/pipeline` keyword in Claude Code hooks.
Ultrawork mode and Ralph Loop are compatible with pipeline execution.
