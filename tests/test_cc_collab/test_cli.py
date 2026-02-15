"""Tests for cc_collab.cli using Click's CliRunner."""

from __future__ import annotations

from click.testing import CliRunner

from cc_collab.cli import cli


class TestCLIRoot:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "cc-collab" in result.output
        assert "validate" in result.output
        assert "run" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

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
        import json
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


class TestCleanupCommand:
    def test_cleanup_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "--retention-days" in result.output

    def test_cleanup_dry_run(self, tmp_path):
        import os
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
