# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-15

### Added
- **ccx-collab CLI tool**: pip-installable unified command interface with 13 subcommands
  - `validate`, `plan`, `split`, `implement`, `merge`, `verify`, `review`, `retrospect` (pipeline stages)
  - `run` (full pipeline execution), `status` (progress dashboard)
  - `health` (CLI tool health check), `cleanup` (old results cleanup), `init` (task template generator)
- **Bridge pattern** (`ccx_collab/bridge.py`): wraps orchestrate.py without code duplication
- **Rich output**: colored console output with tables, panels, progress indicators
- **Parallel subtask execution**: `concurrent.futures.ThreadPoolExecutor` in `ccx-collab run`
- **Simulate mode**: `ccx-collab --simulate run` replaces `SIMULATE_AGENTS=1` env var
- 7-stage pipeline engine (orchestrate.py) with role-based routing (architect/builder)
- Cross-platform support: macOS + Windows (GitHub Actions CI)
- JSON Schema validation for tasks, envelopes, plans, reviews
- Rate limiting with configurable retries (`AGENT_MAX_RETRIES`, `AGENT_RETRY_SLEEP`)
- 267 tests (232 orchestrate + 35 ccx-collab CLI)

### Migration from shell scripts
- `./agent/scripts/pipeline-runner.sh --task X` -> `ccx-collab run --task X`
- `SIMULATE_AGENTS=1 ./pipeline-runner.sh` -> `ccx-collab --simulate run`
- `python3 agent/scripts/orchestrate.py validate-task --task X` -> `ccx-collab validate --task X`
- `./agent/scripts/cleanup-results.sh` -> `ccx-collab cleanup`
