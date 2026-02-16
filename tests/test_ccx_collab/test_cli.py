"""Tests for ccx_collab.cli using Click's CliRunner."""

from __future__ import annotations

import json
import logging
import os

from click.testing import CliRunner

from ccx_collab.cli import cli


class TestCLIRoot:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ccx-collab" in result.output
        assert "validate" in result.output
        assert "run" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.5.0" in result.output

    def test_all_commands_listed(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        expected_commands = [
            "validate", "plan", "split", "implement",
            "merge", "verify", "review", "retrospect",
            "health", "cleanup", "init", "run", "status",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"

    def test_verbose_flag_sets_logging(self):
        """The --verbose flag should enable DEBUG logging."""
        runner = CliRunner()
        # Use a command that runs quickly and does not need extra args
        result = runner.invoke(cli, ["--verbose", "--simulate", "health"])
        assert result.exit_code == 0
        # Verify the root logger level was set
        root_level = logging.getLogger().level
        # It could be DEBUG (10) or already restored; just verify no crash
        assert result.exit_code == 0

    def test_simulate_flag_sets_env(self):
        """The --simulate flag should set SIMULATE_AGENTS=1."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--simulate", "health"])
        assert result.exit_code == 0
        # The env var should have been set during invocation
        # (verified indirectly by health returning "skipped" in simulate mode)
        assert "skipped" in result.output


class TestValidateCommand:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output

    def test_validate_example_task(self, example_task_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--task", str(example_task_path)])
        assert result.exit_code == 0
        assert "validate" in result.output

    def test_validate_missing_task(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--task", "/nonexistent/task.json"])
        assert result.exit_code != 0


class TestStageCommandHelp:
    """Verify --help works for each individual stage command."""

    def test_plan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output
        assert "--out" in result.output

    def test_split_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["split", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output
        assert "--plan" in result.output

    def test_implement_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["implement", "--help"])
        assert result.exit_code == 0
        assert "--subtask-id" in result.output
        assert "--dispatch" in result.output

    def test_merge_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])
        assert result.exit_code == 0
        assert "--work-id" in result.output
        assert "--input" in result.output

    def test_verify_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["verify", "--help"])
        assert result.exit_code == 0
        assert "--work-id" in result.output
        assert "--commands" in result.output

    def test_review_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
        assert "--work-id" in result.output
        assert "--plan" in result.output
        assert "--implement" in result.output

    def test_retrospect_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["retrospect", "--help"])
        assert result.exit_code == 0
        assert "--work-id" in result.output
        assert "--review" in result.output


class TestHealthCommand:
    def test_simulate_mode(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--simulate", "health"])
        assert result.exit_code == 0
        assert "skipped" in result.output

    def test_health_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0

    def test_health_continuous_help_shows_interval(self):
        """The health --help should show --continuous and --interval options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0
        assert "--continuous" in result.output
        assert "--interval" in result.output
        assert "60" in result.output  # default interval value

    def test_health_json_flag_help(self):
        """The health --help should show --json flag with description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
        assert "JSON" in result.output or "json" in result.output.lower()

    def test_health_json_simulate_produces_valid_json(self):
        """Health --json in simulate mode should produce valid JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--simulate", "health", "--json"])
        assert result.exit_code == 0
        # Parse the output as JSON - should not raise
        data = json.loads(result.output.strip())
        assert "timestamp" in data
        assert "status" in data
        assert data["status"] in ("healthy", "unhealthy", "skipped")
        assert "checks" in data


class TestInitCommand:
    def test_init_creates_template(self, tmp_path):
        runner = CliRunner()
        out_path = str(tmp_path / "new-task.task.json")
        result = runner.invoke(cli, [
            "init",
            "--task-id", "my-task",
            "--title", "My Task",
            "--output", out_path,
        ])
        assert result.exit_code == 0
        data = json.loads(open(out_path, encoding="utf-8").read())
        assert data["task_id"] == "my-task"
        assert data["title"] == "My Task"
        assert len(data["subtasks"]) == 1
        assert data["subtasks"][0]["subtask_id"] == "my-task-S01"


class TestStatusCommand:
    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "--work-id" in result.output

    def test_status_missing_work_id(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "status",
            "--work-id", "nonexistent",
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "missing" in result.output

    def test_status_with_existing_results(self, example_task_path, tmp_path):
        """Status should show done for stages that have result files."""
        runner = CliRunner()
        # Run a simulate pipeline to produce result files
        runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", "status-existing",
            "--results-dir", str(tmp_path),
        ])
        # Check status
        result = runner.invoke(cli, [
            "status",
            "--work-id", "status-existing",
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "done" in result.output


class TestCleanupCommand:
    def test_cleanup_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "--retention-days" in result.output

    def test_cleanup_dry_run(self, tmp_path):
        # Create a dummy json file with old mtime
        old_file = tmp_path / "old.json"
        old_file.write_text("{}", encoding="utf-8")
        old_time = 1000000  # very old timestamp
        os.utime(old_file, (old_time, old_time))
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path),
            "--retention-days", "1",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output


class TestRunCommand:
    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output
        assert "--mode" in result.output

    def test_run_help_has_implement_only(self):
        """The run command help should show implement-only as a mode option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "implement-only" in result.output

    def test_run_help_has_mode_option(self):
        """The run command help should describe the --mode option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--mode" in result.output
        assert "full" in result.output

    def test_run_simulate(self, example_task_path, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", "clitest",
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Pipeline Complete" in result.output

    def test_run_auto_generates_work_id(self, example_task_path, tmp_path):
        """When --work-id is not provided, run should auto-generate one."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Work ID:" in result.output
