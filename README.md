**English** | [한국어](README.ko.md)

# Claude Code + Codex CLI Collaboration System

A CI/CD collaboration system where Claude Code CLI (architect) and Codex CLI (builder) work together to execute automated development pipelines.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Runner                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Validate │→ │   Plan   │→ │  Split   │→ │ Implement  │  │
│  │   Task   │  │ (Claude) │  │   Task   │  │(Claude/    │  │
│  └──────────┘  └──────────┘  └──────────┘  │ Codex)     │  │
│                                            └──────┬─────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │        │
│  │Retrospect│← │  Review  │← │  Verify  │← ───────┘        │
│  │          │  │  (Gate)  │  │  (Test)  │  Merge Results   │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

- **Role-based routing**: Automatically selects the appropriate CLI tool based on `architect` (Claude) / `builder` (Codex) roles
- **Automatic chunk splitting**: Automatically splits implementation work into 30-90 minute units
- **Cross-platform**: Simultaneous macOS/Windows support (GitHub Actions CI)
- **Simulation mode**: Validate pipelines without actual CLI calls using `SIMULATE_AGENTS=1`
- **Quality gates**: Strict pass/fail criteria enforced at each stage -- Plan, Implement, Verify, Review

## Quick Start

### Installation

```bash
git clone <repository-url>
cd Claude_Codex_Collaboration
pip install -r requirements.txt
```

### Run in Simulation Mode (no CLI required)

```bash
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id demo
```

### Run with Actual CLI Integration

```bash
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]'

./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id my-work
```

### Step-by-Step Manual Execution

```bash
# 1. Validate task
python3 agent/scripts/orchestrate.py validate-task \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/validation_demo.json

# 2. Plan (Claude)
python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/plan_demo.json

# 3. Split task
python3 agent/scripts/orchestrate.py split-task \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json

# 4. Implement (Codex/Claude)
python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id demo-S01 --work-id demo \
  --out agent/results/implement_demo_S01.json

# 5. Merge results
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --out agent/results/implement_demo.json

# 6. Verify
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo --platform mac \
  --out agent/results/verify_demo.json

# 7. Review gate
python3 agent/scripts/orchestrate.py run-review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo.json \
  --out agent/results/review_demo.json

# 8. Retrospect
python3 agent/scripts/orchestrate.py run-retrospect \
  --work-id demo --review agent/results/review_demo.json \
  --out agent/results/retrospect_demo.json
```

## cc-collab CLI

`cc-collab` is a unified CLI tool that replaces the shell scripts and `orchestrate.py` workflow above. Built on [Click](https://click.palletsprojects.com/) and [Rich](https://rich.readthedocs.io/).

### Installation

```bash
pip install -e .
cc-collab --version
```

### Run Full Pipeline

```bash
# Simulation mode (no actual CLI calls)
cc-collab --simulate run --task agent/tasks/example.task.json

# Run with actual CLI integration
cc-collab run --task agent/tasks/example.task.json --work-id my-feature
```

### Run Individual Stages

```bash
cc-collab validate --task agent/tasks/example.task.json --out results/validation.json
cc-collab plan --task agent/tasks/example.task.json --out results/plan.json
cc-collab split --task agent/tasks/example.task.json --plan results/plan.json --out results/dispatch.json
cc-collab implement --task agent/tasks/example.task.json --dispatch results/dispatch.json --subtask-id S01 --out results/impl_S01.json
cc-collab merge --work-id demo --input "results/impl_*.json" --out results/implement.json
cc-collab verify --work-id demo --out results/verify.json
cc-collab review --work-id demo --plan results/plan.json --implement results/implement.json --verify results/verify.json --out results/review.json
cc-collab retrospect --work-id demo --review results/review.json --out results/retrospect.json
```

### Utility Commands

```bash
cc-collab health                          # Check CLI tool availability
cc-collab status --work-id my-feature     # Query pipeline progress
cc-collab cleanup --retention-days 7      # Clean up old result files
cc-collab init --task-id FEAT-001 --title "New feature"  # Generate task template
```

### Global Options

| Option | Shorthand | Description |
|--------|-----------|-------------|
| `--verbose` | `-v` | Enable DEBUG-level logging |
| `--simulate` | | Simulation mode (no actual CLI calls) |
| `--version` | | Print version information |

For a detailed command reference, see [docs/CC_COLLAB_CLI.md](docs/CC_COLLAB_CLI.md).

## Project Structure

```
├── agent/
│   ├── scripts/
│   │   ├── orchestrate.py          # Core orchestration engine
│   │   ├── pipeline-runner.sh      # Full pipeline runner (bash)
│   │   ├── pipeline-runner.ps1     # Windows PowerShell runner
│   │   ├── claude-wrapper.sh       # Claude CLI wrapper
│   │   └── codex-wrapper.sh        # Codex CLI wrapper
│   ├── schemas/                    # JSON schema contracts
│   │   ├── task.schema.json
│   │   ├── cli-envelope.schema.json
│   │   ├── plan-result.schema.json
│   │   ├── implement-result.schema.json
│   │   └── review-result.schema.json
│   ├── tasks/                      # Input task definitions
│   ├── tests/                      # pytest test suite
│   └── pipeline-config.json        # Pipeline configuration
├── cc_collab/                      # cc-collab CLI package
│   ├── __init__.py                 # Package initialization and version info
│   ├── cli.py                      # Click CLI entry point
│   ├── bridge.py                   # orchestrate.py bridge layer
│   ├── config.py                   # Project settings and platform detection
│   ├── output.py                   # Rich-based output helpers
│   └── commands/                   # CLI command modules
│       ├── stages.py               # Pipeline stage commands (8 stages)
│       ├── pipeline.py             # run, status commands
│       └── tools.py                # health, cleanup, init utilities
├── tests/
│   └── test_cc_collab/             # cc-collab CLI tests
│       ├── test_cli.py             # CLI entry point tests
│       ├── test_bridge.py          # Bridge layer tests
│       └── test_commands.py        # Command tests
├── docs/
│   └── CC_COLLAB_CLI.md            # cc-collab CLI reference documentation
├── .github/workflows/
│   └── agent-orchestrator.yml      # CI/CD pipeline
├── pyproject.toml                  # Python package configuration (cc-collab)
├── CLAUDE.md                       # Claude Code instructions
├── AGENTS.md                       # Agent role definitions
└── requirements.txt                # Python dependencies
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_CODE_CMD` | Claude Code CLI execution command | (required) |
| `CODEX_CLI_CMD` | Codex CLI execution command | (required) |
| `VERIFY_COMMANDS` | Verification commands (JSON array string) | See pipeline-config.json |
| `SIMULATE_AGENTS` | Simulation mode (`1` = enabled) | `0` |
| `AGENT_MAX_RETRIES` | Maximum retry count for CLI calls | `2` |
| `AGENT_RETRY_SLEEP` | Retry wait time in seconds | `20` |

## Development Setup

### Installing Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to automatically check code quality on each commit.

```bash
pip install pre-commit
pre-commit install
```

After installation, running `git commit` will automatically perform the following checks:

- **ruff lint** -- Lint checks on `agent/` and `cc_collab/` Python files (E, F, W rules)
- **ruff format check** -- Formatting checks on `agent/` and `cc_collab/` Python files
- **check-json** -- Syntax validation of `agent/schemas/` JSON files
- **validate-schemas** -- JSON Schema specification validity checks
- **end-of-file-fixer / trailing-whitespace** -- Auto-fix end-of-file newlines and trailing whitespace
- **check-yaml** -- YAML file syntax validation

To temporarily skip hook checks, use the `--no-verify` flag:

```bash
git commit --no-verify -m "Emergency fix"
```

> **Note**: Use `--no-verify` only in urgent situations. Always follow up by running `pre-commit run --all-files` to perform a full check afterward.

## Testing

```bash
# Run all tests
python3 -m pytest agent/tests/ -v

# E2E simulation test
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json --work-id test-e2e
```

## License

This project is distributed under the [MIT License](LICENSE).
