# AGENTS.md — Claude Code + Codex CLI Collaboration Protocol

## Architecture

Each OS (Mac/Windows) runs the full 6-stage pipeline independently:
**Plan → Split → Implement → Verify → Review → Retrospect**

Two AI CLI tools collaborate within each system:
- **Claude Code CLI** (`claude --print`) — architect role
- **Codex CLI** (`codex --approval-mode full-auto --quiet`) — builder role

## Roles

| Role | Agent | Responsibility |
|------|-------|---------------|
| `architect` | Claude Code | Planning, design, review, strategic decisions |
| `builder` | Codex | Implementation, code execution, testing |

Roles are assigned per subtask via the `role` field in `task.schema.json`.
Backward compatible: `owner: "claude"` maps to `architect`, `owner: "codex"` maps to `builder`.

## CLI Contract

### Input
Wrappers receive JSON payload via **stdin** (from `orchestrate.py run_agent_command`).

### Output
Wrappers output a JSON envelope to **stdout**:
```json
{
  "status": "passed|failed",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "result": { "structured": "data" }
}
```

Schema: `agent/schemas/cli-envelope.schema.json`

## Quality Gates

- `verify=skipped` → **fail** (all verification is mandatory)
- `VERIFY_COMMANDS` not set → **pipeline fail**
- `go_no_go` only passes when plan `status == "done"` AND all verify `status == "passed"`
- `build_report_status` treats `skipped` as `failed`

## Git Conventions

Commit format: `[claude|codex] phase: description`
- `[claude] plan: initial architecture design`
- `[codex] implement: add user auth module`
- `[claude] review: approve v1 implementation`

## File Structure

```
agent/
  scripts/
    orchestrate.py          # Core orchestration engine
    claude-wrapper.sh/.ps1  # Claude CLI wrapper
    codex-wrapper.sh/.ps1   # Codex CLI wrapper
    pipeline-runner.sh/.ps1 # Full pipeline executor
  schemas/                  # JSON schemas for all stages
  tasks/                    # Task definitions
  results/                  # Generated results (gitignored)
    mac/                    # macOS pipeline results
    win/                    # Windows pipeline results
  pipeline-config.json      # Pipeline configuration
```

## Running

```bash
# Simulate full pipeline (no real CLI calls)
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id test001

# Real execution (requires CLI tools installed)
./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/my-task.json \
  --work-id work001
```
