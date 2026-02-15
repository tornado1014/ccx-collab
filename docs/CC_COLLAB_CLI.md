# cc-collab CLI Reference

`cc-collab` is a unified command-line interface for the Claude Code + Codex CLI collaboration pipeline. It replaces the shell-script-based workflow (`pipeline-runner.sh`, `orchestrate.py`) with a single, ergonomic CLI tool built on [Click](https://click.palletsprojects.com/) and [Rich](https://rich.readthedocs.io/).

**Version:** 0.1.0

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Global Options](#global-options)
- [Commands](#commands)
  - [Pipeline Stages](#pipeline-stages)
    - [validate](#validate)
    - [plan](#plan)
    - [split](#split)
    - [implement](#implement)
    - [merge](#merge)
    - [verify](#verify)
    - [review](#review)
    - [retrospect](#retrospect)
  - [Pipeline Runner](#pipeline-runner)
    - [run](#run)
    - [status](#status)
  - [Utilities](#utilities)
    - [health](#health)
    - [cleanup](#cleanup)
    - [init](#init)
- [Environment Variables](#environment-variables)
- [Migration Guide](#migration-guide)

---

## Installation

### From source (editable mode)

```bash
cd Claude_Codex_Collaboration
pip install -e .
```

### Verify installation

```bash
cc-collab --version
# cc-collab, version 0.1.0
```

### Dependencies

The following Python packages are installed automatically:

| Package       | Version  | Purpose                        |
|---------------|----------|--------------------------------|
| `click`       | >= 8.0   | CLI framework                  |
| `rich`        | >= 13.0  | Formatted terminal output      |
| `jsonschema`  | >= 4.0   | Task JSON schema validation    |

Python 3.9 or later is required.

---

## Quick Start

### Run the full pipeline in simulation mode (no real CLI calls)

```bash
cc-collab --simulate run --task agent/tasks/example.task.json
```

### Run the full pipeline with real CLI tools

```bash
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]'

cc-collab run --task agent/tasks/example.task.json --work-id my-feature
```

### Run a single stage manually

```bash
cc-collab validate --task agent/tasks/example.task.json --work-id demo --out results/validation.json
```

### Check pipeline progress

```bash
cc-collab status --work-id my-feature
```

### Create a new task template

```bash
cc-collab init --task-id FEAT-001 --title "Add authentication module"
```

---

## Global Options

These options must be placed **before** the subcommand name.

| Option         | Short | Description                                                |
|----------------|-------|------------------------------------------------------------|
| `--verbose`    | `-v`  | Enable verbose (DEBUG-level) logging output                |
| `--simulate`   |       | Run in simulation mode -- no real Claude/Codex CLI calls   |
| `--version`    |       | Show version number and exit                               |
| `--help`       |       | Show help message and exit                                 |

**Example:**

```bash
# Verbose + simulation mode
cc-collab -v --simulate run --task agent/tasks/example.task.json

# Show version
cc-collab --version
```

---

## Commands

### Pipeline Stages

These commands correspond to the 8 stages of the collaboration pipeline. Each stage can be run independently for manual step-by-step execution.

---

#### validate

Validate a task JSON file against the project schema (`agent/schemas/task.schema.json`).

```
cc-collab validate [OPTIONS]
```

| Option       | Required | Default | Description                |
|--------------|----------|---------|----------------------------|
| `--task`     | Yes      |         | Path to task JSON file     |
| `--work-id`  | No       | `""`    | Work ID                    |
| `--out`      | No       | `""`    | Output path for results    |

**Examples:**

```bash
# Basic validation
cc-collab validate --task agent/tasks/example.task.json

# With output file
cc-collab validate \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/validation_demo.json
```

---

#### plan

Run the planning phase. Uses Claude Code CLI (architect role) to generate an execution plan.

```
cc-collab plan [OPTIONS]
```

| Option       | Required | Default | Description                |
|--------------|----------|---------|----------------------------|
| `--task`     | Yes      |         | Path to task JSON file     |
| `--work-id`  | No       | `""`    | Work ID                    |
| `--out`      | Yes      |         | Output path for plan JSON  |

**Examples:**

```bash
cc-collab plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json

# Simulation mode (no real Claude CLI call)
cc-collab --simulate plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json
```

---

#### split

Split a task into execution subtasks based on the plan. Produces a dispatch manifest with subtask assignments (architect/builder roles).

```
cc-collab split [OPTIONS]
```

| Option            | Required | Default | Description                              |
|-------------------|----------|---------|------------------------------------------|
| `--task`          | Yes      |         | Path to task JSON file                   |
| `--plan`          | No       | `""`    | Path to plan result JSON                 |
| `--out`           | Yes      |         | Output path for dispatch JSON            |
| `--matrix-output` | No       | `""`    | Dispatch matrix output path (CI/CD use)  |

**Examples:**

```bash
cc-collab split \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json

# With CI matrix output for GitHub Actions
cc-collab split \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json \
  --matrix-output agent/results/dispatch_demo.matrix.json
```

---

#### implement

Execute a single subtask implementation. Routes to Claude Code CLI or Codex CLI based on the subtask's assigned role.

```
cc-collab implement [OPTIONS]
```

| Option         | Required | Default | Description                  |
|----------------|----------|---------|------------------------------|
| `--task`       | Yes      |         | Path to task JSON file       |
| `--dispatch`   | No       | `""`    | Path to dispatch JSON        |
| `--subtask-id` | Yes      |         | Subtask ID to execute        |
| `--work-id`    | No       | `""`    | Work ID                      |
| `--out`        | Yes      |         | Output path for result JSON  |

**Examples:**

```bash
cc-collab implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id demo-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json

# In simulation mode
cc-collab --simulate implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id demo-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json
```

---

#### merge

Merge multiple implementation result files into a single consolidated result.

```
cc-collab merge [OPTIONS]
```

| Option       | Required | Default       | Description                       |
|--------------|----------|---------------|-----------------------------------|
| `--work-id`  | Yes      |               | Work ID                           |
| `--kind`     | No       | `"implement"` | Merge kind                        |
| `--input`    | Yes      |               | Input file glob pattern           |
| `--out`      | Yes      |               | Output path for merged result     |
| `--dispatch` | No       | `""`          | Path to dispatch JSON             |

**Examples:**

```bash
cc-collab merge \
  --work-id demo \
  --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --out agent/results/implement_demo.json

# With dispatch for subtask-aware merging
cc-collab merge \
  --work-id demo \
  --input "agent/results/implement_demo_*.json" \
  --dispatch agent/results/dispatch_demo.json \
  --out agent/results/implement_demo.json
```

---

#### verify

Run verification commands (tests, linters, etc.) against the implementation output.

```
cc-collab verify [OPTIONS]
```

| Option       | Required | Default          | Description                                             |
|--------------|----------|------------------|---------------------------------------------------------|
| `--work-id`  | Yes      |                  | Work ID                                                 |
| `--platform` | No       | auto-detected    | Platform: `macos`, `linux`, or `windows`                |
| `--out`      | Yes      |                  | Output path for verify result JSON                      |
| `--commands` | No       | `""`             | Verify commands (JSON array or semicolon-separated)     |

Platform is auto-detected from the current system if not specified.

**Examples:**

```bash
# Auto-detect platform, use configured verify commands
cc-collab verify \
  --work-id demo \
  --out agent/results/verify_demo.json

# Explicit platform and commands
cc-collab verify \
  --work-id demo \
  --platform macos \
  --commands '["python3 -m pytest agent/tests/ -v", "ruff check ."]' \
  --out agent/results/verify_demo_macos.json

# Semicolon-separated commands
cc-collab verify \
  --work-id demo \
  --commands "python3 -m pytest;ruff check ." \
  --out agent/results/verify_demo.json
```

---

#### review

Run the review gate. Compares plan, implementation, and verification results to determine pass/fail status.

```
cc-collab review [OPTIONS]
```

| Option        | Required | Default | Description                                      |
|---------------|----------|---------|--------------------------------------------------|
| `--work-id`   | Yes      |         | Work ID                                          |
| `--plan`      | Yes      |         | Path to plan result JSON                         |
| `--implement` | Yes      |         | Path to implement result JSON                    |
| `--verify`    | No       |         | Path(s) to verify result JSON (repeatable)       |
| `--out`       | Yes      |         | Output path for review result JSON               |

The `--verify` option can be specified multiple times to include results from multiple platforms.

**Examples:**

```bash
# Single platform verification
cc-collab review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo_macos.json \
  --out agent/results/review_demo.json

# Multiple platform verifications
cc-collab review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo_macos.json \
  --verify agent/results/verify_demo_windows.json \
  --out agent/results/review_demo.json
```

---

#### retrospect

Generate a retrospective analysis and next-action plan based on the review results.

```
cc-collab retrospect [OPTIONS]
```

| Option       | Required | Default | Description                         |
|--------------|----------|---------|-------------------------------------|
| `--work-id`  | Yes      |         | Work ID                             |
| `--review`   | Yes      |         | Path to review result JSON          |
| `--out`      | Yes      |         | Output path for retrospective JSON  |

**Examples:**

```bash
cc-collab retrospect \
  --work-id demo \
  --review agent/results/review_demo.json \
  --out agent/results/retrospect_demo.json
```

---

### Pipeline Runner

These commands manage end-to-end pipeline execution and monitoring.

---

#### run

Run the full 7-stage pipeline in one command. Automatically executes: validate, plan, split, implement (parallel subtasks), merge, verify, review, and retrospect.

```
cc-collab run [OPTIONS]
```

| Option          | Required | Default           | Description                                       |
|-----------------|----------|-------------------|---------------------------------------------------|
| `--task`        | Yes      |                   | Path to task JSON file                            |
| `--work-id`     | No       | auto-generated    | Work ID (SHA-256 hash of task file if omitted)    |
| `--results-dir` | No       | `agent/results`   | Directory for result files                        |
| `--mode`        | No       | `full`            | Pipeline mode: `full` or `implement-only`         |

In `full` mode, all 7 stages run. In `implement-only` mode, the pipeline stops after merge (stages 1-5), skipping verify, review, and retrospect.

Subtasks are executed in parallel (up to 4 concurrent workers).

**Examples:**

```bash
# Full pipeline, auto-generated work ID
cc-collab run --task agent/tasks/example.task.json

# Named work ID, custom results directory
cc-collab run \
  --task agent/tasks/example.task.json \
  --work-id my-feature \
  --results-dir output/

# Implement-only mode (skip verify/review/retrospect)
cc-collab run \
  --task agent/tasks/example.task.json \
  --work-id my-feature \
  --mode implement-only

# Simulation mode (no real CLI calls)
cc-collab --simulate run --task agent/tasks/example.task.json
```

---

#### status

Show pipeline progress for a given work ID. Displays a Rich-formatted table with each stage's completion status and result.

```
cc-collab status [OPTIONS]
```

| Option          | Required | Default         | Description                    |
|-----------------|----------|-----------------|--------------------------------|
| `--work-id`     | Yes      |                 | Work ID to check               |
| `--results-dir` | No       | `agent/results` | Results directory to inspect   |

**Example:**

```bash
cc-collab status --work-id my-feature
```

Sample output:

```
          Pipeline Status: my-feature
┌─────────────┬──────────────────────────────────┬─────────┬────────┐
│ Stage       │ File                             │ Status  │ Result │
├─────────────┼──────────────────────────────────┼─────────┼────────┤
│ validate    │ validation_my-feature.json       │ done    │ passed │
│ plan        │ plan_my-feature.json             │ done    │ passed │
│ split       │ dispatch_my-feature.json         │ done    │ passed │
│ implement   │ implement_my-feature.json        │ done    │ passed │
│ verify      │ verify_my-feature_macos.json     │ done    │ passed │
│ review      │ review_my-feature.json           │ done    │ passed │
│ retrospect  │ retrospect_my-feature.json       │ missing │        │
└─────────────┴──────────────────────────────────┴─────────┴────────┘
```

---

### Utilities

---

#### health

Check that required CLI tools (Claude Code, Codex CLI) are accessible and responsive.

```
cc-collab health [OPTIONS]
```

| Option  | Required | Default | Description                          |
|---------|----------|---------|--------------------------------------|
| `--out` | No       | `""`    | Output path for health check results |

**Examples:**

```bash
# Quick health check
cc-collab health

# Save results to file
cc-collab health --out agent/results/health.json
```

---

#### cleanup

Clean up old pipeline result files based on a retention period.

```
cc-collab cleanup [OPTIONS]
```

| Option             | Required | Default         | Description                              |
|--------------------|----------|-----------------|------------------------------------------|
| `--results-dir`    | No       | `agent/results` | Results directory                        |
| `--retention-days` | No       | `30`            | Keep files newer than N days             |
| `--dry-run`        | No       | `false`         | Preview deletions without executing      |

**Examples:**

```bash
# Preview what would be deleted (dry run)
cc-collab cleanup --dry-run

# Delete files older than 7 days
cc-collab cleanup --retention-days 7

# Clean a specific directory
cc-collab cleanup --results-dir output/results --retention-days 14
```

---

#### init

Create a new task template file interactively. Generates a valid task JSON with placeholder acceptance criteria and subtasks.

```
cc-collab init [OPTIONS]
```

| Option      | Required | Default                              | Description                    |
|-------------|----------|--------------------------------------|--------------------------------|
| `--task-id` | Yes      | (prompted if not provided)           | Unique task identifier         |
| `--title`   | Yes      | (prompted if not provided)           | Human-readable title           |
| `--output`  | No       | `agent/tasks/{task_id}.task.json`    | Output file path               |

If `--task-id` or `--title` are not provided on the command line, the tool prompts for them interactively.

**Examples:**

```bash
# Interactive mode (prompts for task ID and title)
cc-collab init

# Non-interactive with all options
cc-collab init --task-id FEAT-042 --title "Implement caching layer"

# Custom output path
cc-collab init \
  --task-id FEAT-042 \
  --title "Implement caching layer" \
  --output tasks/caching.task.json
```

Generated template structure:

```json
{
  "task_id": "FEAT-042",
  "title": "Implement caching layer",
  "scope": "Implementation scope for Implement caching layer",
  "risk_level": "medium",
  "priority": "medium",
  "acceptance_criteria": [
    {
      "id": "AC-S00-1",
      "description": "PLACEHOLDER: Define overall acceptance criteria",
      "verification": "echo 'FAIL: acceptance criteria not yet defined' && exit 1",
      "type": "automated"
    }
  ],
  "subtasks": [
    {
      "subtask_id": "FEAT-042-S01",
      "title": "First subtask",
      "role": "builder",
      "acceptance_criteria": [
        {
          "id": "AC-S01-1",
          "description": "PLACEHOLDER: Define subtask criteria",
          "verification": "echo 'FAIL: subtask criteria not yet defined' && exit 1",
          "type": "automated"
        }
      ]
    }
  ]
}
```

---

## Environment Variables

| Variable             | Description                                      | Default                           |
|----------------------|--------------------------------------------------|-----------------------------------|
| `CLAUDE_CODE_CMD`    | Claude Code CLI execution command                | (required for real execution)     |
| `CODEX_CLI_CMD`      | Codex CLI execution command                      | (required for real execution)     |
| `VERIFY_COMMANDS`    | Verification commands (JSON array string)        | From `pipeline-config.json`       |
| `SIMULATE_AGENTS`    | Simulation mode (`1` = enabled)                  | `0`                               |
| `AGENT_MAX_RETRIES`  | Max CLI call retry count                         | `2`                               |
| `AGENT_RETRY_SLEEP`  | Retry wait time in seconds                       | `20`                              |
| `CLAUDE_CODEX_ROOT`  | Override project root detection                  | auto-detected                     |

**Note:** When using `cc-collab --simulate`, the tool sets `SIMULATE_AGENTS=1` automatically. You do not need to set it manually.

### Typical environment setup

```bash
# Real CLI execution
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]'

# Or simulation mode (no real CLI tools needed)
# Just pass --simulate to cc-collab
```

---

## Migration Guide

This section maps the legacy shell-script and `orchestrate.py` commands to their `cc-collab` equivalents.

### Full pipeline execution

**Before (shell script):**

```bash
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id demo
```

**After (cc-collab):**

```bash
cc-collab --simulate run \
  --task agent/tasks/example.task.json \
  --work-id demo
```

### Individual stage commands

**Before (orchestrate.py):**

```bash
python3 agent/scripts/orchestrate.py validate-task \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/validation_demo.json
```

**After (cc-collab):**

```bash
cc-collab validate \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/validation_demo.json
```

### Full command mapping table

| Legacy Command (`orchestrate.py`)                    | cc-collab Equivalent               |
|------------------------------------------------------|-------------------------------------|
| `python3 agent/scripts/orchestrate.py validate-task` | `cc-collab validate`               |
| `python3 agent/scripts/orchestrate.py run-plan`      | `cc-collab plan`                   |
| `python3 agent/scripts/orchestrate.py split-task`    | `cc-collab split`                  |
| `python3 agent/scripts/orchestrate.py run-implement` | `cc-collab implement`              |
| `python3 agent/scripts/orchestrate.py merge-results` | `cc-collab merge`                  |
| `python3 agent/scripts/orchestrate.py run-verify`    | `cc-collab verify`                 |
| `python3 agent/scripts/orchestrate.py run-review`    | `cc-collab review`                 |
| `python3 agent/scripts/orchestrate.py run-retrospect`| `cc-collab retrospect`             |
| `./agent/scripts/pipeline-runner.sh --task ...`      | `cc-collab run --task ...`         |
| (no equivalent)                                       | `cc-collab status --work-id ...`   |
| (no equivalent)                                       | `cc-collab health`                 |
| (no equivalent)                                       | `cc-collab cleanup`                |
| (no equivalent)                                       | `cc-collab init`                   |

### Key differences

1. **Global options come first.** With `cc-collab`, flags like `--simulate` and `--verbose` go before the subcommand:
   ```bash
   # Correct
   cc-collab --simulate validate --task ...

   # Incorrect
   cc-collab validate --simulate --task ...
   ```

2. **Simulation mode is a flag, not an env var.** Use `--simulate` instead of `SIMULATE_AGENTS=1` (though the env var still works).

3. **`--verify` is repeatable in review.** Pass multiple verification result files:
   ```bash
   cc-collab review --verify file1.json --verify file2.json ...
   ```

4. **Auto-generated work IDs.** The `run` command generates a work ID from the task file hash when `--work-id` is omitted.

5. **Rich output.** All commands use Rich for colored, formatted terminal output. Use `--verbose` for debug-level logging.
