# Contributing to ccx-collab

Thank you for your interest in contributing to ccx-collab. This document provides
guidelines and instructions for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Getting Started

### Prerequisites

- **Python 3.9+** (3.11 or 3.12 recommended)
- **pip** (latest version)
- **git**

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/user/Claude_Codex_Collaboration.git
cd Claude_Codex_Collaboration

# Install in development mode (recommended)
pip install -e ".[dev]"

# Alternative: install with requirements file
pip install -e . && pip install -r requirements.txt
```

### Verify Installation

```bash
ccx-collab --help
ccx-collab --version
```

You should see the CLI help output listing all available subcommands
(validate, plan, split, implement, merge, verify, review, retrospect, run,
status, health, cleanup, init).

## Development Workflow

1. **Create a feature branch from main.**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes.** See [Project Structure](#project-structure) for an
   overview of where code lives, and [ARCHITECTURE.md](ARCHITECTURE.md) for
   detailed design documentation.

3. **Run the test suite.**

   ```bash
   python3 -m pytest tests/test_ccx_collab/ agent/tests/ -v
   ```

4. **Run the linter and formatter.**

   ```bash
   ruff check .
   ruff format --check .
   ```

5. **Commit with a descriptive message.** Follow the conventions visible in
   `git log --oneline` -- a short summary line describing the change, optionally
   followed by a blank line and a longer explanation.

   ```bash
   git add <files>
   git commit -m "Add retry logic to health check command"
   ```

6. **Push and open a pull request.**

   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

### Linting and Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. The lint configuration selects rules `E`, `F`, and `W` (pycodestyle
errors, Pyflakes, and pycodestyle warnings) with `E501` (line length) ignored.

```bash
# Check for lint issues
ruff check .

# Auto-fix safe lint issues
ruff check --fix .

# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

### Pre-commit Hooks

Install pre-commit hooks to catch issues before they reach CI:

```bash
pip install pre-commit
pre-commit install
```

The following hooks run automatically on every commit:

| Hook | Scope | Description |
|------|-------|-------------|
| `ruff` (lint) | `agent/`, `ccx_collab/` | Lint Python files |
| `ruff-format` | `agent/`, `ccx_collab/` | Check formatting |
| `check-json` | `agent/schemas/*.json` | Validate JSON syntax |
| `validate-schemas` | `agent/schemas/*.json` | Validate JSON Schema structure (Draft 7) |
| `check-yaml` | all YAML files | Validate YAML syntax |
| `end-of-file-fixer` | all files | Ensure files end with newline |
| `trailing-whitespace` | all files | Remove trailing whitespace |

In emergencies you can skip hooks with `git commit --no-verify`, but please run
`pre-commit run --all-files` afterward to verify compliance.

### Conventions

- **Type hints** are encouraged but not mandatory. New public functions should
  include type annotations where practical.
- **Docstrings** are expected for all public functions and classes. Use the
  `"""One-line summary."""` or NumPy-style format for multi-line docstrings.
- **Logging** uses the standard library `logging` module. Each module creates
  its own logger with `logger = logging.getLogger(__name__)`. Use `logger.debug`
  for internal tracing and `logger.error` / `logger.warning` for user-facing
  messages.

## Project Structure

```
Claude_Codex_Collaboration/
├── ccx_collab/                 # Python package (pip-installable CLI)
│   ├── __init__.py            #   Package version
│   ├── cli.py                 #   Click CLI entry point
│   ├── bridge.py              #   Bridge to orchestrate.py
│   ├── config.py              #   Configuration loading and merging
│   ├── output.py              #   Rich console output helpers
│   └── commands/              #   Click subcommand groups
│       ├── stages.py          #     Pipeline stage commands
│       ├── pipeline.py        #     run / status commands
│       └── tools.py           #     health / cleanup / init commands
├── agent/                     # Core engine and CI/CD assets
│   ├── scripts/               #   orchestrate.py + shell/PS1 wrappers
│   ├── schemas/               #   6 JSON Schema files (v1.0.0)
│   ├── tasks/                 #   Task definition templates
│   ├── tests/                 #   Engine-level tests
│   └── results/               #   Pipeline output artifacts
├── tests/                     # CLI-level tests
│   └── test_ccx_collab/        #   Bridge, CLI, command tests
├── docs/                      # Additional documentation
├── .github/workflows/         # CI/CD (orchestrator + PyPI publish)
├── pyproject.toml             # Build config and metadata
├── requirements.txt           # Runtime + dev dependencies
├── Dockerfile                 # Container image definition
├── docker-compose.yml         # Docker Compose service
├── ARCHITECTURE.md            # Technical architecture document
└── CHANGELOG.md               # Release notes
```

For detailed design information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing

### Running Tests

```bash
# Run the full test suite (435+ tests)
python3 -m pytest tests/test_ccx_collab/ agent/tests/ -v

# Run only CLI tests
python3 -m pytest tests/test_ccx_collab/ -v

# Run only engine tests
python3 -m pytest agent/tests/ -v

# Run a specific test by name
python3 -m pytest -k "test_validate_missing_task"

# Run tests with short tracebacks
python3 -m pytest tests/test_ccx_collab/ agent/tests/ -v --tb=short
```

### Test Organization

- **`agent/tests/`** -- Unit tests for the orchestration engine
  (`test_orchestrate.py`), JSON schema validation (`test_schemas.py`),
  wrapper scripts (`test_wrappers.py`), and cleanup utilities
  (`test_cleanup.py`).
- **`tests/test_ccx_collab/`** -- Tests for the CLI layer including bridge
  functions (`test_bridge.py`), Click commands (`test_cli.py`), and
  subcommand behavior (`test_commands.py`).

### Test Naming Convention

Follow the pattern `test_<function>_<scenario>`:

```python
def test_validate_missing_task_file():
    ...

def test_run_merge_no_input_glob_returns_error():
    ...

def test_health_check_json_output_format():
    ...
```

### Markers

- `@pytest.mark.windows` -- Tests specific to Windows behavior. Deselect on
  other platforms with `-m "not windows"`.

### Coverage

The project currently has 435+ tests. When adding new features, include
corresponding tests. Do not reduce overall test coverage.

## Pull Request Process

1. **One feature per PR.** Keep pull requests focused on a single change to make
   review manageable.

2. **Include tests** for any new functionality or bug fixes. Tests should cover
   both success and failure paths.

3. **Update documentation** if your change affects user-facing behavior. This
   includes `CLAUDE.md`, `CHANGELOG.md`, and command help text.

4. **All CI checks must pass.** The GitHub Actions workflow runs:
   - Ruff lint
   - Full test suite on macOS and Windows
   - Pipeline simulation run
   - Schema validation

5. **Write a clear PR description.** Explain what the change does, why it is
   needed, and any design decisions made.

6. **Keep commits clean.** Squash fixup commits before requesting review when
   appropriate.

## Reporting Issues

### Bug Reports

When filing a bug report, include:

- **Steps to reproduce** -- Minimal set of commands or actions to trigger the
  issue.
- **Expected behavior** -- What you expected to happen.
- **Actual behavior** -- What actually happened, including error messages and
  stack traces.
- **Environment** -- Python version, operating system, ccx-collab version
  (`ccx-collab --version`), and installation method (pip, Docker, development).

### Feature Requests

When proposing a new feature, include:

- **Use case** -- Describe the problem you are trying to solve.
- **Proposed solution** -- Outline your suggested approach.
- **Alternatives considered** -- Mention any other approaches you evaluated.

## License

By contributing to ccx-collab, you agree that your contributions will be licensed
under the [MIT License](LICENSE).
