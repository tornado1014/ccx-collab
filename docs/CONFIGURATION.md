# Configuration Reference

cc-collab uses a 4-layer configuration system with clear precedence rules.

## Configuration Precedence

Settings are resolved in this order (highest priority first):

1. **CLI Flags** -- `cc-collab --verbose --simulate run ...`
2. **Project Config** -- `.cc-collab.yaml` in project root
3. **User Config** -- `~/.cc-collab/config.yaml`
4. **Built-in Defaults** -- hardcoded sensible defaults

Higher-priority settings override lower-priority ones. When a key appears in
multiple layers, only the highest-priority value is used.

## Configuration Files

### Project Config (`.cc-collab.yaml`)

Place in your project root directory. This file is typically shared with your
team via version control.

```yaml
# .cc-collab.yaml (project root)
simulate: false
verbose: false
results_dir: "agent/results"
verify_commands:
  - "python3 -m pytest agent/tests/ -v"
```

The project root is detected automatically by walking up the directory tree
looking for an `agent/` directory. You can override this with the
`CLAUDE_CODEX_ROOT` environment variable.

### User Config (`~/.cc-collab/config.yaml`)

Personal preferences that apply across all projects. Useful for settings like
`verbose` that you always want enabled during development.

```yaml
# ~/.cc-collab/config.yaml
verbose: true
retention_days: 14
```

## Available Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `verbose` | bool | `false` | Enable debug logging output |
| `simulate` | bool | `false` | Simulate agent calls (no real CLI invocations) |
| `results_dir` | string | `"agent/results"` | Directory for pipeline result JSON files |
| `retention_days` | int | `30` | Days to keep result files before cleanup considers them old |
| `verify_commands` | list[string] | `["python3 -m pytest agent/tests/ -v"]` | Commands to run during the verify stage |

### Setting Details

#### `verbose`

When enabled, configures the root logger to `DEBUG` level with timestamped
output. When disabled, only `WARNING` and above are shown.

```yaml
verbose: true
```

Equivalent CLI flag: `--verbose` or `-v`

#### `simulate`

When enabled, sets the `SIMULATE_AGENTS=1` environment variable internally so
that agent CLI calls are simulated rather than executed. This lets you validate
your pipeline configuration without having Claude Code or Codex CLI installed.

```yaml
simulate: true
```

Equivalent CLI flag: `--simulate`

#### `results_dir`

Relative path (from project root) where pipeline result JSON files are written.
The actual on-disk path is resolved as `<project_root>/<results_dir>`.

```yaml
results_dir: "agent/results"
```

#### `retention_days`

Number of days to retain result files. The `cleanup` command uses this value to
decide which result files are old enough to remove.

```yaml
retention_days: 30
```

#### `verify_commands`

A list of shell commands that the `verify` pipeline stage runs to confirm the
implementation is correct. Each command must exit with code 0 to pass.

```yaml
verify_commands:
  - "python3 -m pytest agent/tests/ -v"
  - "python3 -m flake8 cc_collab/"
```

This can also be overridden at runtime via the `VERIFY_COMMANDS` environment
variable (as a JSON array string).

## Pipeline Config (`agent/pipeline-config.json`)

In addition to the YAML configuration layers above, the lower-level orchestrator
reads `agent/pipeline-config.json` for pipeline-specific defaults. This JSON
file controls retry behavior, timeouts, rate limiting, and role definitions.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pipeline_mode` | string | `"local-only"` | Pipeline execution mode |
| `defaults.max_retries` | int | `2` | Max CLI call retry count |
| `defaults.retry_sleep_seconds` | int | `20` | Seconds to wait between retries |
| `defaults.cli_timeout_seconds` | int | `300` | Timeout per CLI invocation (seconds) |
| `defaults.rate_limit_seconds` | int | `2` | Minimum seconds between CLI calls |
| `defaults.log_level` | string | `"INFO"` | Orchestrator log level |
| `defaults.result_retention_days` | int | `30` | Result file retention (days) |
| `defaults.results_dir_pattern` | string | `"agent/results/{os_prefix}/{work_id}"` | Result directory path pattern |
| `default_verify_commands` | list[string] | (see below) | Fallback verify commands |
| `roles.architect.env_var` | string | `"CLAUDE_CODE_CMD"` | Env var for architect CLI path |
| `roles.builder.env_var` | string | `"CODEX_CLI_CMD"` | Env var for builder CLI path |

Default verify commands in `pipeline-config.json`:

```json
[
  "python3 -m pytest agent/tests/ -v --tb=short",
  "python3 -c \"import json,pathlib; [json.loads(p.read_text()) for p in pathlib.Path('agent/schemas').glob('*.json')]\""
]
```

## Environment Variables

These environment variables affect pipeline behavior. They are read by the
orchestrator (`agent/scripts/orchestrate.py`) and by cc-collab internals.

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMULATE_AGENTS` | Set to `1` or `true` to enable simulation mode | `0` |
| `CLAUDE_CODEX_ROOT` | Override automatic project root detection | auto-detected |
| `CLAUDE_CODE_CMD` | Path/command for Claude Code CLI (architect role) | (required for real execution) |
| `CODEX_CLI_CMD` | Path/command for Codex CLI (builder role) | (required for real execution) |
| `VERIFY_COMMANDS` | Verification commands as a JSON array string | From `pipeline-config.json` |
| `AGENT_MAX_RETRIES` | Override max CLI call retry count | `2` |
| `AGENT_RETRY_SLEEP` | Override retry wait time in seconds | `20` |
| `AGENT_RATE_LIMIT` | Override rate limit between CLI calls (seconds) | `2` |
| `CLI_TIMEOUT_SECONDS` | Override per-invocation CLI timeout (seconds) | `300` |

**Note:** When using `cc-collab --simulate`, the tool sets `SIMULATE_AGENTS=1`
automatically. You do not need to set it manually.

### Typical Environment Setup

```bash
# Real CLI execution
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]'

# Run the pipeline
cc-collab run --task agent/tasks/example.task.json --work-id demo
```

```bash
# Simulation mode (no real CLI tools needed)
cc-collab --simulate run --task agent/tasks/example.task.json --work-id demo
```

## CLI Flag Overrides

The top-level `--verbose` and `--simulate` flags override their corresponding
config file values:

```bash
# Override verbose from config
cc-collab --verbose run --task task.json --work-id demo

# Override simulate from config
cc-collab --simulate health

# Combine both
cc-collab --verbose --simulate run --task task.json --work-id demo
```

These flags use `default=None` internally so that cc-collab can distinguish
between "not provided" (use config file value) and "explicitly set" (override
config file value).

## Examples

See `docs/examples/` for complete example configuration files:

- [`cc-collab.minimal.yaml`](examples/cc-collab.minimal.yaml) -- bare minimum
  configuration
- [`cc-collab.full.yaml`](examples/cc-collab.full.yaml) -- all available options
  with documentation

## Configuration Loading Internals

For developers working on cc-collab itself, the configuration system is
implemented in `cc_collab/config.py`:

- `CC_COLLAB_DEFAULTS` -- dict of built-in default values
- `load_cc_collab_config()` -- merges all 4 layers and returns a final dict
- `_load_yaml_file()` -- safely loads a single YAML file with error handling
- `get_project_root()` -- detects project root via directory traversal or
  `CLAUDE_CODEX_ROOT` env var
- `get_platform()` -- returns `"macos"`, `"linux"`, or `"windows"`
- `load_pipeline_config()` -- loads `agent/pipeline-config.json`
