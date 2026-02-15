"""Integration tests for cc-collab commands."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

from click.testing import CliRunner

from cc_collab.cli import cli


class TestValidateIntegration:
    def test_validate_with_output(self, sample_task, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "val.json")
        result = runner.invoke(cli, [
            "validate",
            "--task", str(sample_task),
            "--out", out,
        ])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert data["status"] == "ready"
        assert data["work_id"] == "test-task-001"

    def test_validate_bad_task(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"task_id": "x"}', encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--task", str(bad)])
        # Should fail validation (exit 2) due to missing required fields
        assert result.exit_code != 0


class TestPipelineSimulateIntegration:
    def test_full_pipeline(self, example_task_path, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", "inttest",
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Pipeline Complete" in result.output

        # Verify all result files exist
        expected_files = [
            "validation_inttest.json",
            "plan_inttest.json",
            "dispatch_inttest.json",
            "implement_inttest.json",
            "review_inttest.json",
            "retrospect_inttest.json",
        ]
        for fname in expected_files:
            fpath = tmp_path / fname
            assert fpath.exists(), f"Expected {fname} to exist"
            data = json.loads(fpath.read_text(encoding="utf-8"))
            assert "status" in data, f"{fname} missing status field"

    def test_implement_only_mode(self, example_task_path, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", "implonly",
            "--results-dir", str(tmp_path),
            "--mode", "implement-only",
        ])
        assert result.exit_code == 0
        assert "implement-only" in result.output
        # Review/retrospect should NOT exist
        assert not (tmp_path / "review_implonly.json").exists()
        assert not (tmp_path / "retrospect_implonly.json").exists()


class TestStatusIntegration:
    def test_status_after_pipeline(self, example_task_path, tmp_path):
        runner = CliRunner()
        # Run pipeline first
        runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", "stattest",
            "--results-dir", str(tmp_path),
        ])
        # Check status
        result = runner.invoke(cli, [
            "status",
            "--work-id", "stattest",
            "--results-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "done" in result.output


class TestInitIntegration:
    def test_init_produces_valid_task(self, tmp_path):
        runner = CliRunner()
        out_path = str(tmp_path / "new.task.json")
        result = runner.invoke(cli, [
            "init",
            "--task-id", "init-test",
            "--title", "Init Test Task",
            "--output", out_path,
        ])
        assert result.exit_code == 0

        # Validate the created task
        result2 = runner.invoke(cli, [
            "validate",
            "--task", out_path,
        ])
        assert result2.exit_code == 0

    def test_init_with_custom_output_path(self, tmp_path):
        """Init writes to a custom output path when --output is provided."""
        custom_dir = tmp_path / "custom" / "subdir"
        out_path = str(custom_dir / "my-task.task.json")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "init",
            "--task-id", "custom-path-task",
            "--title", "Custom Path Task",
            "--output", out_path,
        ])
        assert result.exit_code == 0
        assert Path(out_path).exists()
        data = json.loads(Path(out_path).read_text(encoding="utf-8"))
        assert data["task_id"] == "custom-path-task"

    def test_init_default_output_path_construction(self, tmp_path, monkeypatch):
        """When --output is empty, init constructs a default path from task_id."""
        # Change cwd to tmp_path so the default path writes there
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "init",
            "--task-id", "auto-path-task",
            "--title", "Auto Path Task",
            # No --output: will use default agent/tasks/{task_id}.task.json
        ])
        assert result.exit_code == 0
        expected = Path("agent/tasks/auto-path-task.task.json")
        assert expected.exists()
        data = json.loads(expected.read_text(encoding="utf-8"))
        assert data["task_id"] == "auto-path-task"


class TestCleanupIntegration:
    def test_cleanup_no_old_files(self, tmp_path):
        """Cleanup with no old files (all files are recent) should delete nothing."""
        recent = tmp_path / "recent.json"
        recent.write_text("{}", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path),
            "--retention-days", "1",
        ])
        assert result.exit_code == 0
        assert recent.exists(), "Recent file should NOT have been deleted"

    def test_cleanup_nonexistent_directory(self, tmp_path):
        """Cleanup on a non-existent directory should fail gracefully."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0

    def test_cleanup_invalid_retention_zero(self, tmp_path):
        """Cleanup with --retention-days=0 should fail."""
        (tmp_path / "dummy.json").write_text("{}", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path),
            "--retention-days", "0",
        ])
        assert result.exit_code != 0

    def test_cleanup_invalid_retention_negative(self, tmp_path):
        """Cleanup with --retention-days=-1 should fail."""
        (tmp_path / "dummy.json").write_text("{}", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path),
            "--retention-days", "-1",
        ])
        assert result.exit_code != 0

    def test_cleanup_live_deletes_old(self, tmp_path):
        """Cleanup in live mode (no --dry-run) should actually delete old files."""
        old_file = tmp_path / "old_result.json"
        old_file.write_text("{}", encoding="utf-8")
        old_time = 1000000  # very old timestamp
        os.utime(old_file, (old_time, old_time))
        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(tmp_path),
            "--retention-days", "1",
        ])
        assert result.exit_code == 0
        assert not old_file.exists(), "Old file should have been deleted"


class TestMergeCommand:
    """Tests for the merge command parameter handling."""

    def _create_impl_files(self, directory, work_id, count=2):
        """Helper: create dummy implementation result files in directory."""
        for i in range(count):
            result = {
                "status": "passed",
                "subtask_id": f"{work_id}-S{i:02d}",
                "files_changed": [f"file{i}.py"],
                "commands_executed": [],
            }
            path = directory / f"implement_{work_id}_{work_id}-S{i:02d}.json"
            path.write_text(json.dumps(result), encoding="utf-8")

    def test_merge_with_explicit_input_glob(self, tmp_path):
        """Merge with --input should use the explicit glob pattern."""
        work_id = "merge-input-test"
        self._create_impl_files(tmp_path, work_id)
        out = str(tmp_path / f"implement_{work_id}.json")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "merge",
            "--work-id", work_id,
            "--input", str(tmp_path / f"implement_{work_id}_*.json"),
            "--out", out,
        ])
        assert result.exit_code == 0, f"merge --input failed: {result.output}"
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        # Merge wraps subtask results; status reflects the merged outcome
        assert data["status"] in ("passed", "done"), (
            f"Unexpected merge status: {data['status']}"
        )

    def test_merge_with_results_dir(self, tmp_path):
        """Merge with --results-dir should auto-construct the glob."""
        work_id = "merge-dir-test"
        self._create_impl_files(tmp_path, work_id)
        out = str(tmp_path / f"implement_{work_id}.json")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "merge",
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
            "--out", out,
        ])
        assert result.exit_code == 0, f"merge --results-dir failed: {result.output}"
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        # Merge wraps subtask results; status reflects the merged outcome
        assert data["status"] in ("passed", "done"), (
            f"Unexpected merge status: {data['status']}"
        )

    def test_merge_help_shows_both_options(self):
        """Merge --help should document both --input and --results-dir."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--results-dir" in result.output
        # Check that the help text explains both approaches
        assert "glob pattern" in result.output.lower() or "glob" in result.output.lower()

    def test_merge_neither_option_gives_error(self, tmp_path):
        """Merge with neither --input nor --results-dir should fail with exit code != 0."""
        out = str(tmp_path / "merge_out.json")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "merge",
            "--work-id", "no-input-test",
            "--out", out,
        ])
        assert result.exit_code != 0, (
            "merge should fail when neither --input nor --results-dir is provided"
        )


class TestConfigModule:
    def test_get_project_root(self):
        from cc_collab.config import get_project_root
        root = get_project_root()
        assert (root / "agent").is_dir()

    def test_get_platform(self):
        from cc_collab.config import get_platform
        platform = get_platform()
        assert platform in {"macos", "linux", "windows"}

    def test_get_platform_returns_string(self):
        from cc_collab.config import get_platform
        platform = get_platform()
        assert isinstance(platform, str)
        assert len(platform) > 0

    def test_load_pipeline_config(self):
        from cc_collab.config import load_pipeline_config
        config = load_pipeline_config()
        assert "defaults" in config
        assert "roles" in config

    def test_load_pipeline_config_returns_dict(self):
        from cc_collab.config import load_pipeline_config
        config = load_pipeline_config()
        assert isinstance(config, dict)

    def test_get_results_dir(self):
        from cc_collab.config import get_results_dir
        results = get_results_dir()
        assert results.name == "results"
        assert "agent" in str(results)

    def test_get_project_root_via_env(self, tmp_path, monkeypatch):
        """Setting CLAUDE_CODEX_ROOT should override normal root detection."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CODEX_ROOT", str(tmp_path))
        from cc_collab.config import get_project_root
        root = get_project_root()
        assert root == tmp_path


class TestOutputModule:
    def test_console_exists(self):
        from cc_collab.output import console
        assert console is not None

    def test_print_functions_callable(self):
        from cc_collab.output import (
            print_error, print_header, print_stage_result, print_success,
        )
        # Just verify they don't crash
        print_header("Test")
        print_stage_result("test", 0, "/tmp/out.json")
        print_stage_result("test", 1)
        print_error("test error")
        print_success("test success")

    def test_print_error_does_not_crash(self):
        """print_error should handle any string without crashing."""
        from cc_collab.output import print_error
        print_error("")
        print_error("Simple error message")
        print_error("Error with special chars: <>&\"'")

    def test_print_success_does_not_crash(self):
        """print_success should handle any string without crashing."""
        from cc_collab.output import print_success
        print_success("")
        print_success("All tests passed")
        print_success("Path: /tmp/some/result.json")

    def test_print_pipeline_header(self):
        """print_pipeline_header should produce output without crashing."""
        from cc_collab.output import print_pipeline_header
        # Should not raise any exception
        print_pipeline_header("task.json", "work-123", "full")
        print_pipeline_header("another.json", "w-456", "implement-only")

    def test_print_json_result(self):
        """print_json_result should render JSON data without crashing."""
        from cc_collab.output import print_json_result
        print_json_result({"status": "passed", "count": 3})
        print_json_result({})

    def test_print_stage_result_with_output_path(self):
        """print_stage_result should include the output path in the message."""
        from cc_collab.output import print_stage_result
        # These should not raise
        print_stage_result("validate", 0, "/tmp/validation.json")
        print_stage_result("implement", 2, "/tmp/implement.json")
        print_stage_result("verify", 0)
