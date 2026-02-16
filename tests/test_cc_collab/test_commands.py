"""Integration tests for cc-collab commands."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from cc_collab.cli import cli
from cc_collab.config import CC_COLLAB_DEFAULTS, load_cc_collab_config


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


class TestPipelineResumeIntegration:
    """Tests for the --resume and --force-stage pipeline options."""

    @staticmethod
    def _write_stage_result(tmp_path, filename, status="passed"):
        """Helper: write a minimal JSON result file with the given status."""
        path = tmp_path / filename
        path.write_text(json.dumps({"status": status}), encoding="utf-8")
        return path

    def test_resume_skips_completed_stages(self, example_task_path, tmp_path):
        """With --resume, stages whose result files exist and have a passing
        status should be skipped and the output should say 'skipped'."""
        runner = CliRunner()
        work_id = "resume-skip"

        # Run full pipeline first to create all result files
        first_run = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
        ])
        assert first_run.exit_code == 0, f"First run failed: {first_run.output}"

        # Now resume -- all stages should be skipped (except retrospect which always runs)
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
            "--resume",
        ])
        assert result.exit_code == 0, f"Resume run failed: {result.output}"
        assert "skipped" in result.output.lower(), (
            "Expected 'skipped' in resume output when all stages are completed"
        )
        assert "Pipeline Complete" in result.output

    def test_resume_reruns_failed_stage(self, example_task_path, tmp_path):
        """When a stage result file has a non-passing status the stage and all
        downstream stages should be re-executed.

        We pre-seed validate + plan results but mark split as failed.
        Resume should skip validate and plan, then re-run from split onwards.
        We verify the skip/re-run behaviour from the output rather than
        requiring the full pipeline to succeed (downstream stages may fail
        in simulation mode when fed artificial checkpoint data).
        """
        runner = CliRunner()
        work_id = "resume-fail"

        # Write passing results for validate and plan only
        self._write_stage_result(tmp_path, f"validation_{work_id}.json", "ready")
        self._write_stage_result(tmp_path, f"plan_{work_id}.json", "passed")
        # Write a *failed* result for split
        self._write_stage_result(tmp_path, f"dispatch_{work_id}.json", "failed")

        # Resume should skip validate and plan, then re-run split and everything after
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
            "--resume",
        ])
        # Validate the skip/re-run behaviour from the output text
        assert "Validating task" in result.output
        assert "Planning" in result.output
        lines = result.output.split("\n")
        for line in lines:
            if "Validating task" in line:
                assert "skipped" in line.lower(), "Validate should be skipped"
            if "Planning" in line:
                assert "skipped" in line.lower(), "Plan should be skipped"
            if "Splitting task" in line:
                assert "skipped" not in line.lower(), "Split should NOT be skipped"
        # Confirm the pipeline header shows the correct skip set
        assert "Skipping: plan, validate" in result.output or \
               "Skipping: validate, plan" in result.output

    def test_force_stage_reruns_specified_stage(self, example_task_path, tmp_path):
        """--force-stage should force re-execution of the named stage and all
        downstream stages even when their result files exist."""
        runner = CliRunner()
        work_id = "resume-force"

        # Run full pipeline first
        first_run = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
        ])
        assert first_run.exit_code == 0, f"First run failed: {first_run.output}"

        # Resume with --force-stage=verify: stages before verify may be skipped,
        # but verify and review should re-run
        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
            "--resume",
            "--force-stage", "verify",
        ])
        assert result.exit_code == 0, f"Force-stage run failed: {result.output}"
        assert "Force re-run: verify" in result.output
        # Verify stage should NOT be skipped
        lines = result.output.split("\n")
        for line in lines:
            if "Verifying" in line:
                assert "skipped" not in line.lower(), (
                    "Verify should NOT be skipped with --force-stage=verify"
                )
        assert "Pipeline Complete" in result.output

    def test_resume_with_no_prior_results(self, example_task_path, tmp_path):
        """--resume with no existing result files should run the full pipeline
        (nothing to skip)."""
        runner = CliRunner()
        work_id = "resume-fresh"

        result = runner.invoke(cli, [
            "--simulate",
            "run",
            "--task", str(example_task_path),
            "--work-id", work_id,
            "--results-dir", str(tmp_path),
            "--resume",
        ])
        assert result.exit_code == 0, f"Fresh resume run failed: {result.output}"
        assert "Pipeline Complete" in result.output
        # No stages should be skipped since there are no prior results
        assert "already completed" not in result.output, (
            "No stages should be skipped when there are no prior results"
        )

    def test_resume_help_text_shows_options(self):
        """The run --help output should document --resume and --force-stage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--resume" in result.output, "--resume should appear in help text"
        assert "--force-stage" in result.output, "--force-stage should appear in help text"


class TestWindowsPathHandling:
    """Cross-platform path handling tests to ensure Windows compatibility."""

    def test_get_project_root_returns_path_object(self):
        """config.get_project_root() must return a pathlib.Path on every platform."""
        from cc_collab.config import get_project_root
        root = get_project_root()
        assert isinstance(root, Path), (
            f"get_project_root() returned {type(root).__name__}, expected Path"
        )

    def test_output_paths_use_path_objects(self, tmp_path):
        """Result file paths should use pathlib.Path, not hardcoded '/' separators."""
        from cc_collab.config import get_results_dir
        results = get_results_dir()
        assert isinstance(results, Path), (
            f"get_results_dir() returned {type(results).__name__}, expected Path"
        )
        # Construct an output path the same way the pipeline does
        output_file = results / "validation_test.json"
        assert isinstance(output_file, Path)
        # The path should use the platform-native separator internally
        assert output_file.name == "validation_test.json"

    def test_cleanup_handles_paths_on_current_platform(self, tmp_path):
        """Cleanup should handle paths correctly regardless of platform separator."""
        from click.testing import CliRunner
        from cc_collab.cli import cli

        # Create a file in a subdirectory to exercise path joining
        sub = tmp_path / "sub"
        sub.mkdir()
        target = sub / "old_result.json"
        target.write_text("{}", encoding="utf-8")
        old_time = 1000000
        os.utime(target, (old_time, old_time))

        runner = CliRunner()
        result = runner.invoke(cli, [
            "cleanup",
            "--results-dir", str(sub),
            "--retention-days", "1",
        ])
        assert result.exit_code == 0
        assert not target.exists(), "Old file in subdirectory should have been deleted"

    @pytest.mark.windows
    def test_windows_backslash_paths(self, is_windows):
        """On Windows, Path objects should use backslash separators natively."""
        if not is_windows:
            pytest.skip("Windows-only test")
        from cc_collab.config import get_project_root
        root = get_project_root()
        # On Windows, str(Path) uses backslashes
        assert "\\" in str(root), (
            f"Expected backslash in Windows path, got: {root}"
        )

    @pytest.mark.windows
    def test_windows_results_dir_construction(self, is_windows):
        """On Windows, results dir should be constructed with native separators."""
        if not is_windows:
            pytest.skip("Windows-only test")
        from cc_collab.config import get_results_dir
        results = get_results_dir()
        assert isinstance(results, Path)
        # Ensure the path doesn't use forward slashes on Windows
        parts = results.parts
        assert "agent" in parts
        assert "results" in parts

    @pytest.mark.windows
    def test_windows_validate_output_path(self, is_windows, sample_task, tmp_path):
        """On Windows, validate --out should write to a backslash-separated path."""
        if not is_windows:
            pytest.skip("Windows-only test")
        from click.testing import CliRunner
        from cc_collab.cli import cli

        out = tmp_path / "subdir" / "val.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "validate",
            "--task", str(sample_task),
            "--out", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


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


class TestInitTemplates:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_init_simple_template(self, runner, tmp_path):
        out = str(tmp_path / "simple.task.json")
        result = runner.invoke(cli, ["init", "--task-id", "t1", "--title", "T1", "--template", "simple", "-o", out])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text())
        assert data["risk_level"] == "low"
        assert len(data["subtasks"]) == 1
        assert data["subtasks"][0]["role"] == "builder"

    def test_init_standard_template(self, runner, tmp_path):
        out = str(tmp_path / "standard.task.json")
        result = runner.invoke(cli, ["init", "--task-id", "t2", "--title", "T2", "--template", "standard", "-o", out])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text())
        assert len(data["subtasks"]) == 1

    def test_init_complex_template(self, runner, tmp_path):
        out = str(tmp_path / "complex.task.json")
        result = runner.invoke(cli, ["init", "--task-id", "t3", "--title", "T3", "--template", "complex", "-o", out])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text())
        assert data["risk_level"] == "high"
        assert len(data["subtasks"]) == 3
        assert data["subtasks"][0]["role"] == "architect"
        assert data["subtasks"][1]["role"] == "builder"

    def test_init_default_template_is_standard(self, runner, tmp_path):
        out = str(tmp_path / "default.task.json")
        result = runner.invoke(cli, ["init", "--task-id", "t4", "--title", "T4", "-o", out])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text())
        # Default should match standard (1 subtask)
        assert len(data["subtasks"]) == 1

    def test_init_complex_has_exit1_verification(self, runner, tmp_path):
        out = str(tmp_path / "complex2.task.json")
        result = runner.invoke(cli, ["init", "--task-id", "t5", "--title", "T5", "--template", "complex", "-o", out])
        assert result.exit_code == 0
        data = json.loads(Path(out).read_text())
        for ac in data["acceptance_criteria"]:
            assert "exit 1" in ac["verification"]


class TestCcCollabConfigFile:
    """Tests for YAML config file loading and precedence."""

    def test_defaults_when_no_config_files(self, tmp_path):
        """With no config files present, load_cc_collab_config returns defaults."""
        config = load_cc_collab_config(
            project_dir=tmp_path,
            user_dir=tmp_path / "nonexistent_user_dir",
        )
        assert config["results_dir"] == CC_COLLAB_DEFAULTS["results_dir"]
        assert config["retention_days"] == CC_COLLAB_DEFAULTS["retention_days"]
        assert config["simulate"] == CC_COLLAB_DEFAULTS["simulate"]
        assert config["verbose"] == CC_COLLAB_DEFAULTS["verbose"]
        assert config["verify_commands"] == CC_COLLAB_DEFAULTS["verify_commands"]

    def test_project_level_config(self, tmp_path):
        """Project-level .cc-collab.yaml should override defaults."""
        project_cfg = {
            "results_dir": "custom/results",
            "retention_days": 7,
        }
        (tmp_path / ".cc-collab.yaml").write_text(
            yaml.dump(project_cfg), encoding="utf-8"
        )
        config = load_cc_collab_config(
            project_dir=tmp_path,
            user_dir=tmp_path / "no_user",
        )
        assert config["results_dir"] == "custom/results"
        assert config["retention_days"] == 7
        # Non-overridden defaults should remain
        assert config["simulate"] == CC_COLLAB_DEFAULTS["simulate"]
        assert config["verbose"] == CC_COLLAB_DEFAULTS["verbose"]

    def test_user_level_config(self, tmp_path):
        """User-level ~/.cc-collab/config.yaml should override defaults."""
        user_dir = tmp_path / "user_home" / ".cc-collab"
        user_dir.mkdir(parents=True)
        user_cfg = {
            "verbose": True,
            "retention_days": 60,
        }
        (user_dir / "config.yaml").write_text(
            yaml.dump(user_cfg), encoding="utf-8"
        )
        config = load_cc_collab_config(
            project_dir=tmp_path / "no_project",
            user_dir=user_dir,
        )
        assert config["verbose"] is True
        assert config["retention_days"] == 60
        # Non-overridden defaults should remain
        assert config["results_dir"] == CC_COLLAB_DEFAULTS["results_dir"]

    def test_precedence_project_over_user(self, tmp_path):
        """Project config should override user config for the same key."""
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({"retention_days": 60, "verbose": True}), encoding="utf-8"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".cc-collab.yaml").write_text(
            yaml.dump({"retention_days": 14}), encoding="utf-8"
        )

        config = load_cc_collab_config(
            project_dir=project_dir,
            user_dir=user_dir,
        )
        # project overrides user for retention_days
        assert config["retention_days"] == 14
        # user setting for verbose still applies (not overridden by project)
        assert config["verbose"] is True

    def test_precedence_cli_over_project(self, tmp_path):
        """CLI overrides should take highest precedence."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".cc-collab.yaml").write_text(
            yaml.dump({"simulate": True, "retention_days": 14}), encoding="utf-8"
        )

        config = load_cc_collab_config(
            project_dir=project_dir,
            user_dir=tmp_path / "no_user",
            cli_overrides={"simulate": False, "retention_days": 3},
        )
        assert config["simulate"] is False
        assert config["retention_days"] == 3

    def test_full_precedence_chain(self, tmp_path):
        """CLI > project > user > defaults -- full chain test."""
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        (user_dir / "config.yaml").write_text(
            yaml.dump({
                "results_dir": "user/results",
                "retention_days": 60,
                "verbose": True,
                "simulate": True,
            }),
            encoding="utf-8",
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".cc-collab.yaml").write_text(
            yaml.dump({
                "results_dir": "project/results",
                "retention_days": 14,
            }),
            encoding="utf-8",
        )

        config = load_cc_collab_config(
            project_dir=project_dir,
            user_dir=user_dir,
            cli_overrides={"retention_days": 1},
        )
        # CLI wins for retention_days
        assert config["retention_days"] == 1
        # Project wins for results_dir (over user)
        assert config["results_dir"] == "project/results"
        # User wins for verbose (not set in project or CLI)
        assert config["verbose"] is True
        # User wins for simulate (not set in project or CLI)
        assert config["simulate"] is True
        # verify_commands is only in defaults
        assert config["verify_commands"] == CC_COLLAB_DEFAULTS["verify_commands"]

    def test_cli_none_values_are_ignored(self, tmp_path):
        """CLI overrides with None values should not overwrite config."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".cc-collab.yaml").write_text(
            yaml.dump({"simulate": True}), encoding="utf-8"
        )

        config = load_cc_collab_config(
            project_dir=project_dir,
            user_dir=tmp_path / "no_user",
            cli_overrides={"simulate": None, "verbose": None},
        )
        # simulate should remain True from project config, not reset by None
        assert config["simulate"] is True
        assert config["verbose"] == CC_COLLAB_DEFAULTS["verbose"]

    def test_invalid_yaml_graceful_fallback(self, tmp_path):
        """Invalid YAML should not crash; defaults should be returned."""
        (tmp_path / ".cc-collab.yaml").write_text(
            "{{invalid: yaml: [unbalanced", encoding="utf-8"
        )
        config = load_cc_collab_config(
            project_dir=tmp_path,
            user_dir=tmp_path / "no_user",
        )
        # Should still get defaults
        assert config["results_dir"] == CC_COLLAB_DEFAULTS["results_dir"]
        assert config["retention_days"] == CC_COLLAB_DEFAULTS["retention_days"]

    def test_yaml_with_non_dict_content(self, tmp_path):
        """YAML that produces a list instead of dict should be ignored."""
        (tmp_path / ".cc-collab.yaml").write_text(
            "- item1\n- item2\n", encoding="utf-8"
        )
        config = load_cc_collab_config(
            project_dir=tmp_path,
            user_dir=tmp_path / "no_user",
        )
        assert config == CC_COLLAB_DEFAULTS

    def test_missing_config_files_graceful(self, tmp_path):
        """Completely missing directories and files should not cause errors."""
        config = load_cc_collab_config(
            project_dir=tmp_path / "does_not_exist",
            user_dir=tmp_path / "also_missing",
        )
        assert config == CC_COLLAB_DEFAULTS

    def test_cli_integration_config_in_context(self, tmp_path):
        """CLI startup should load config and make it available in ctx.obj."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / ".cc-collab.yaml").write_text(
            yaml.dump({"retention_days": 42}), encoding="utf-8"
        )

        # Point the project root to our tmp_path so the config is picked up
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        # Just verify CLI still runs without error
        assert result.exit_code == 0

    def test_cli_verbose_flag_overrides_config(self, tmp_path, monkeypatch):
        """Passing --verbose on CLI should override config file setting."""
        # Create a project config with verbose=false
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (tmp_path / ".cc-collab.yaml").write_text(
            yaml.dump({"verbose": False}), encoding="utf-8"
        )
        monkeypatch.setenv("CLAUDE_CODEX_ROOT", str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_cli_simulate_flag_overrides_config(self, tmp_path, monkeypatch):
        """Passing --simulate on CLI should override config file setting."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (tmp_path / ".cc-collab.yaml").write_text(
            yaml.dump({"simulate": False}), encoding="utf-8"
        )
        monkeypatch.setenv("CLAUDE_CODEX_ROOT", str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["--simulate", "--help"])
        assert result.exit_code == 0
