# Architecture

Technical architecture documentation for the ccx-collab pipeline system.

## Table of Contents

- [System Overview](#system-overview)
- [Component Diagram](#component-diagram)
- [Bridge Pattern](#bridge-pattern)
- [Pipeline Architecture](#pipeline-architecture)
- [Configuration System](#configuration-system)
- [Schema System](#schema-system)
- [Testing Strategy](#testing-strategy)
- [Deployment](#deployment)

## System Overview

ccx-collab orchestrates Claude Code CLI and Codex CLI to perform automated
development cycles. A task definition (JSON) enters the system and flows
through a 7-stage pipeline where an **architect** (Claude Code) handles
planning and review while a **builder** (Codex CLI) handles implementation.

The pipeline stages execute in order:

```
validate -> plan -> split -> implement -> merge -> verify -> review
```

Each stage produces a JSON result file that feeds into the next stage.
A final **retrospect** step generates lessons learned after the review gate.

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                       ccx-collab CLI                          │
│  Entry point: ccx_collab/cli.py                               │
│  Framework:   Click + Rich                                   │
│  Commands:    13 subcommands (8 stages + 5 tools)            │
├──────────────────────────────────────────────────────────────┤
│                       bridge.py                              │
│  Pattern:     argparse.Namespace adapter                     │
│  Purpose:     Translate Click calls to orchestrate actions   │
├──────────────────────────────────────────────────────────────┤
│                     orchestrate.py                           │
│  Location:    agent/scripts/orchestrate.py (1,476 lines)     │
│  Role:        Core pipeline engine                           │
│  Interface:   action_* functions accepting argparse.Namespace│
├─────────────────────────┬────────────────────────────────────┤
│    Claude Code CLI      │         Codex CLI                  │
│    (architect role)     │         (builder role)             │
│    Planning, review,    │         Implementation,            │
│    retrospective        │         code generation            │
└─────────────────────────┴────────────────────────────────────┘
```

### Module Inventory

| Module | Lines | Responsibility |
|--------|------:|----------------|
| `agent/scripts/orchestrate.py` | 1,476 | Core engine: CLI dispatch, schema validation, stage execution, rate limiting |
| `ccx_collab/cli.py` | 82 | Click group, global options (verbose, simulate), command registration |
| `ccx_collab/bridge.py` | 171 | Namespace adapter between Click and orchestrate action functions |
| `ccx_collab/config.py` | 177 | 4-layer config loading, project root detection, platform detection |
| `ccx_collab/output.py` | 63 | Rich console helpers (headers, stage results, errors, JSON output) |
| `ccx_collab/commands/stages.py` | 180 | 8 Click commands for individual pipeline stages |
| `ccx_collab/commands/pipeline.py` | 349 | `run` (full pipeline) and `status` (progress dashboard) commands |
| `ccx_collab/commands/tools.py` | 252 | `health`, `cleanup`, and `init` utility commands |

## Bridge Pattern

### Problem

The core pipeline engine (`orchestrate.py`) was originally designed as a
standalone script with an `argparse`-based CLI. Rewriting it to use Click
directly would be a large, risky change with no immediate functional benefit.

### Solution

`bridge.py` acts as a thin adapter layer. Each bridge function:

1. Accepts typed Python arguments from the Click command.
2. Constructs an `argparse.Namespace` object with the expected attributes.
3. Calls the corresponding `action_*` function in orchestrate.py.
4. Returns the integer exit code.

```python
# bridge.py (simplified)
def run_validate(task: str, work_id: str = "", out: str = "") -> int:
    args = argparse.Namespace(task=task, work_id=work_id, out=out)
    return orchestrate.action_validate_task(args)
```

### Benefits

- **Zero code duplication.** The engine logic exists in one place.
- **Incremental modernization.** The Click CLI can evolve independently.
  If orchestrate.py is ever refactored to accept plain arguments instead of
  Namespace objects, only bridge.py needs to change.
- **Testability.** Bridge functions can be tested in isolation with any
  combination of arguments, without invoking Click.

### Import Mechanism

`bridge.py` dynamically adds `agent/scripts/` to `sys.path` so that
`orchestrate.py` can be imported as a regular Python module despite not being
inside a package.

## Pipeline Architecture

### 7-Stage Pipeline

| # | Stage | Role | Input | Output |
|---|-------|------|-------|--------|
| 1 | **validate** | system | task JSON | `validation_{work_id}.json` |
| 2 | **plan** | architect | task JSON | `plan_{work_id}.json` |
| 3 | **split** | system | task + plan | `dispatch_{work_id}.json` + `.matrix.json` |
| 4 | **implement** | builder | task + dispatch | `implement_{work_id}_{subtask_id}.json` (per subtask) |
| 5 | **merge** | system | implementation results | `implement_{work_id}.json` |
| 6 | **verify** | system | verification commands | `verify_{work_id}_{platform}.json` |
| 7 | **review** | architect | plan + implement + verify | `review_{work_id}.json` |
| + | **retrospect** | architect | review result | `retrospect_{work_id}.json` |

### Parallel Subtask Execution

Stage 4 (implement) runs subtasks in parallel using
`concurrent.futures.ThreadPoolExecutor` with a maximum of 4 workers:

```python
with ThreadPoolExecutor(max_workers=min(4, len(subtasks))) as executor:
    futures = {executor.submit(_run_subtask, st): st for st in subtasks}
    for future in as_completed(futures):
        rc = future.result()
```

Each subtask is routed to either the architect (Claude Code) or builder
(Codex CLI) based on the `role` field in the dispatch JSON.

### Resume and Checkpoint

The pipeline supports resuming from the last successful stage. When
`--resume` is passed:

1. Each stage's result directory is scanned for files matching
   `{prefix}_{work_id}*.json`.
2. A result file is considered complete if its JSON `status` field is one of
   `passed`, `completed`, `ready`, or `done`.
3. Completed stages are skipped.

The `--force-stage` option forces re-execution of a specific stage and all
downstream stages, even if their result files exist.

```bash
# Resume from where it left off
ccx-collab run --task task.json --work-id abc123 --resume

# Force re-run from verify stage onward
ccx-collab run --task task.json --work-id abc123 --resume --force-stage verify
```

### Rate Limiting

The orchestration engine supports configurable rate limiting for CLI tool
invocations via environment variables:

- `AGENT_MAX_RETRIES` -- Maximum number of retry attempts (default: 3)
- `AGENT_RETRY_SLEEP` -- Seconds to wait between retries (default: 30)

## Configuration System

### 4-Layer Precedence

Configuration values are resolved in order of decreasing precedence:

```
CLI flags  >  project config  >  user config  >  built-in defaults
```

| Layer | Source | Example |
|-------|--------|---------|
| 1. CLI flags | `--verbose`, `--simulate` | `ccx-collab -v run --task ...` |
| 2. Project config | `.ccx-collab.yaml` in project root | `simulate: true` |
| 3. User config | `~/.ccx-collab/config.yaml` | `retention_days: 14` |
| 4. Built-in defaults | `CCX_COLLAB_DEFAULTS` in `config.py` | `verbose: false` |

### Flag Detection

Click options use `default=None` so that the configuration system can
distinguish between "user explicitly passed `--verbose`" and "user did not
provide the flag." Only explicitly provided flags are included in the
CLI overrides dictionary:

```python
@click.option("--verbose", "-v", is_flag=True, default=None)
```

### Built-in Defaults

```python
CCX_COLLAB_DEFAULTS = {
    "results_dir": "agent/results",
    "retention_days": 30,
    "simulate": False,
    "verbose": False,
    "verify_commands": ["python3 -m pytest agent/tests/ -v"],
}
```

### Project Root Detection

The project root is located by walking up the directory tree from either the
package location or the current working directory, looking for a directory
that contains an `agent/` subdirectory. This can be overridden with the
`CLAUDE_CODEX_ROOT` environment variable.

## Schema System

### Schema Inventory

Six JSON Schema files (Draft 7) define the contracts between pipeline stages:

| Schema | Purpose |
|--------|---------|
| `task.schema.json` | Task definition: id, title, scope, subtasks, acceptance criteria |
| `cli-envelope.schema.json` | Standard wrapper for CLI tool responses |
| `plan-result.schema.json` | Planning stage output |
| `implement-result.schema.json` | Implementation stage output |
| `review-result.schema.json` | Review gate output (pass/fail with findings) |
| `retrospect.schema.json` | Retrospective: lessons learned, next actions |

### Versioning Strategy

All schemas enforce version `1.0.0` using a `const` + `default` pattern:

```json
{
  "schema_version": {
    "type": "string",
    "const": "1.0.0",
    "default": "1.0.0"
  }
}
```

The `const` keyword ensures that if a version is provided, it must match
exactly. The `default` keyword makes the field optional -- documents without
an explicit version are treated as `1.0.0`. This provides backward
compatibility: existing documents without a version field remain valid.

### Validation

Schemas are validated at two levels:

1. **Structure validation.** Pre-commit hooks verify that all schema files are
   valid JSON Schema (Draft 7) using `jsonschema.Draft7Validator.check_schema`.
2. **Runtime validation.** The orchestrate engine validates task files and
   stage outputs against their respective schemas during pipeline execution.

## Testing Strategy

### Test Distribution

The project maintains 435+ tests across two test suites:

| Suite | Location | Count | Scope |
|-------|----------|------:|-------|
| Engine tests | `agent/tests/` | ~400 | orchestrate.py, schemas, wrappers, cleanup |
| CLI tests | `tests/test_ccx_collab/` | ~35 | bridge, Click commands, output formatting |

### Test Categories

**Unit tests** (`test_bridge.py`, `test_orchestrate.py`) -- Test individual
functions in isolation. Bridge tests verify that `argparse.Namespace` objects
are constructed correctly. Engine tests cover validation logic, stage
execution, error handling, and edge cases.

**Integration tests** (`test_cli.py`, `test_commands.py`) -- Test CLI commands
end-to-end using Click's `CliRunner`, which invokes commands in-process
without spawning a subprocess:

```python
from click.testing import CliRunner
from ccx_collab.cli import cli

def test_version_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "ccx-collab" in result.output
```

**Schema validation tests** (`test_schemas.py`) -- Verify that all JSON
schemas are valid Draft 7, that example tasks pass validation, and that
invalid documents are correctly rejected.

**Platform-specific tests** -- Tests marked with `@pytest.mark.windows` cover
Windows-specific behavior (PowerShell wrappers, path handling). These are
deselected on other platforms with `-m "not windows"`.

### Simulation Mode

Tests and CI runs use simulation mode (`SIMULATE_AGENTS=1` or
`ccx-collab --simulate`) to avoid making real API calls to Claude Code or
Codex CLI. In simulation mode, wrapper scripts return synthetic responses
that conform to the expected schemas.

## Deployment

### PyPI Package

ccx-collab is distributed as a standard Python package:

```bash
pip install ccx-collab
```

The package is built with setuptools and published via GitHub Actions:

1. Push a version tag (`v0.1.0`) to trigger the publish workflow.
2. The workflow runs the full test suite.
3. Builds sdist and wheel using `python -m build`.
4. Publishes to TestPyPI first, then to PyPI.

The entry point is declared in `pyproject.toml`:

```toml
[project.scripts]
ccx-collab = "ccx_collab.cli:main"
```

### Docker

A container image based on `python:3.12-slim` is provided:

```bash
# Build
docker build -t ccx-collab .

# Run (simulation mode by default)
docker run --rm ccx-collab run --task /app/agent/tasks/example.task.json

# Docker Compose
docker compose run ccx-collab --help
```

The Docker image sets `SIMULATE_AGENTS=1` by default. Override at runtime to
enable real CLI calls:

```bash
docker run --rm -e SIMULATE_AGENTS=0 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  ccx-collab run --task /app/agent/tasks/example.task.json
```

### GitHub Actions CI/CD

Two workflows automate testing and deployment:

**`agent-orchestrator.yml`** -- Runs on every push that modifies task files,
schemas, or the workflow itself. Executes the full pipeline on both macOS and
Windows runners in matrix mode. Uploads pipeline results and JUnit reports as
artifacts.

**`publish-pypi.yml`** -- Triggered by version tags. Runs the test suite,
builds the distribution, publishes to TestPyPI, and conditionally publishes
to PyPI.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SIMULATE_AGENTS` | `0` | Set to `1` to use synthetic CLI responses |
| `CLAUDE_CODE_CMD` | `claude` | Path or command for Claude Code CLI |
| `CODEX_CLI_CMD` | `codex` | Path or command for Codex CLI |
| `VERIFY_COMMANDS` | (none) | Semicolon-separated verification commands |
| `AGENT_MAX_RETRIES` | `3` | Maximum retry attempts for CLI calls |
| `AGENT_RETRY_SLEEP` | `30` | Seconds between retry attempts |
| `CLAUDE_CODEX_ROOT` | (none) | Override project root detection |
