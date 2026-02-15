"""Integration tests for cc-collab commands."""

from __future__ import annotations

import json
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


class TestConfigModule:
    def test_get_project_root(self):
        from cc_collab.config import get_project_root
        root = get_project_root()
        assert (root / "agent").is_dir()

    def test_get_platform(self):
        from cc_collab.config import get_platform
        platform = get_platform()
        assert platform in {"macos", "linux", "windows"}

    def test_load_pipeline_config(self):
        from cc_collab.config import load_pipeline_config
        config = load_pipeline_config()
        assert "defaults" in config
        assert "roles" in config


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
