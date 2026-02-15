"""Tests for cc_collab.bridge module."""

from __future__ import annotations

import json
import os
import sys
import pytest

from cc_collab.bridge import (
    _ensure_orchestrate_importable,
    run_health_check,
    run_implement,
    run_merge,
    run_plan,
    run_retrospect,
    run_review,
    run_split,
    run_validate,
    run_verify,
    setup_simulate_mode,
)


class TestSetupSimulateMode:
    def test_enable(self):
        setup_simulate_mode(True)
        assert os.environ.get("SIMULATE_AGENTS") == "1"

    def test_disable(self):
        os.environ["SIMULATE_AGENTS"] = "1"
        setup_simulate_mode(False)
        assert "SIMULATE_AGENTS" not in os.environ

    def test_disable_when_not_set(self):
        os.environ.pop("SIMULATE_AGENTS", None)
        setup_simulate_mode(False)
        assert "SIMULATE_AGENTS" not in os.environ


class TestRunValidate:
    def test_valid_task(self, sample_task):
        rc = run_validate(task=str(sample_task))
        assert rc == 0

    def test_missing_file(self, tmp_path):
        rc = run_validate(task=str(tmp_path / "nonexistent.json"))
        assert rc == 1

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        rc = run_validate(task=str(bad_file))
        assert rc == 1

    def test_with_output_path(self, sample_task, tmp_path):
        out = str(tmp_path / "validation_result.json")
        rc = run_validate(task=str(sample_task), out=out)
        assert rc == 0
        result = json.loads(open(out, encoding="utf-8").read())
        assert result["status"] == "ready"


class TestRunHealthCheck:
    def test_simulate_mode(self):
        setup_simulate_mode(True)
        rc = run_health_check()
        assert rc == 0

    def test_with_output(self, tmp_path):
        setup_simulate_mode(True)
        out = str(tmp_path / "health.json")
        rc = run_health_check(out=out)
        assert rc == 0
        result = json.loads(open(out, encoding="utf-8").read())
        assert result["status"] == "skipped"


class TestEnsureOrchestrateImportable:
    def test_scripts_dir_in_sys_path(self):
        """Verify that _ensure_orchestrate_importable adds agent/scripts to sys.path."""
        from pathlib import Path

        scripts_dir = str(Path(__file__).resolve().parents[2] / "agent" / "scripts")
        # It should already be in sys.path from the module-level call
        assert scripts_dir in sys.path

    def test_idempotent(self):
        """Calling _ensure_orchestrate_importable multiple times should not duplicate entries."""
        from pathlib import Path

        scripts_dir = str(Path(__file__).resolve().parents[2] / "agent" / "scripts")
        count_before = sys.path.count(scripts_dir)
        _ensure_orchestrate_importable()
        _ensure_orchestrate_importable()
        count_after = sys.path.count(scripts_dir)
        assert count_after == count_before


class TestRunPlan:
    def test_simulate_mode(self, sample_task, tmp_path):
        setup_simulate_mode(True)
        out = str(tmp_path / "plan.json")
        rc = run_plan(task=str(sample_task), work_id="test-plan", out=out)
        assert rc == 0
        data = json.loads(open(out, encoding="utf-8").read())
        assert "status" in data

    def test_missing_task(self, tmp_path):
        out = str(tmp_path / "plan.json")
        rc = run_plan(task=str(tmp_path / "nonexistent.json"), out=out)
        assert rc == 1

    def test_invalid_json_task(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        out = str(tmp_path / "plan.json")
        rc = run_plan(task=str(bad), out=out)
        assert rc == 1


class TestRunSplit:
    def test_with_valid_plan_input(self, sample_task, tmp_path):
        setup_simulate_mode(True)
        # First generate a plan
        plan_out = str(tmp_path / "plan.json")
        run_plan(task=str(sample_task), work_id="split-test", out=plan_out)
        # Then split
        dispatch_out = str(tmp_path / "dispatch.json")
        rc = run_split(task=str(sample_task), plan=plan_out, out=dispatch_out)
        assert rc == 0
        data = json.loads(open(dispatch_out, encoding="utf-8").read())
        assert "subtasks" in data or "status" in data

    def test_without_plan(self, sample_task, tmp_path):
        """Split should still work without a plan file (uses task subtasks directly)."""
        setup_simulate_mode(True)
        dispatch_out = str(tmp_path / "dispatch.json")
        rc = run_split(task=str(sample_task), out=dispatch_out)
        assert rc == 0

    def test_missing_task(self, tmp_path):
        out = str(tmp_path / "dispatch.json")
        rc = run_split(task=str(tmp_path / "nonexistent.json"), out=out)
        assert rc == 1


class TestRunImplement:
    def test_simulate_mode(self, sample_task, tmp_path):
        setup_simulate_mode(True)
        # Create a dispatch file first
        dispatch_out = str(tmp_path / "dispatch.json")
        run_split(task=str(sample_task), out=dispatch_out)
        # Implement a subtask
        impl_out = str(tmp_path / "implement.json")
        rc = run_implement(
            task=str(sample_task),
            dispatch=dispatch_out,
            subtask_id="test-task-001-S01",
            work_id="impl-test",
            out=impl_out,
        )
        assert rc == 0
        data = json.loads(open(impl_out, encoding="utf-8").read())
        assert "status" in data

    def test_missing_task(self, tmp_path):
        impl_out = str(tmp_path / "implement.json")
        rc = run_implement(
            task=str(tmp_path / "nonexistent.json"),
            subtask_id="S01",
            work_id="test",
            out=impl_out,
        )
        assert rc == 1

    def test_nonexistent_subtask_id(self, sample_task, tmp_path):
        """Using a subtask ID that does not exist should fail."""
        setup_simulate_mode(True)
        dispatch_out = str(tmp_path / "dispatch.json")
        run_split(task=str(sample_task), out=dispatch_out)
        impl_out = str(tmp_path / "implement.json")
        rc = run_implement(
            task=str(sample_task),
            dispatch=dispatch_out,
            subtask_id="nonexistent-subtask-id",
            work_id="impl-test",
            out=impl_out,
        )
        assert rc == 1


class TestRunMerge:
    def test_with_results_dir_pattern(self, sample_task, tmp_path):
        """Merge should construct input_glob from results_dir when input_glob is empty."""
        setup_simulate_mode(True)
        # Run plan+split+implement first
        plan_out = str(tmp_path / "plan_merge.json")
        dispatch_out = str(tmp_path / "dispatch_merge.json")
        run_plan(task=str(sample_task), work_id="merge", out=plan_out)
        run_split(task=str(sample_task), plan=plan_out, out=dispatch_out)
        impl_out = str(tmp_path / "implement_merge_test-task-001-S01.json")
        run_implement(
            task=str(sample_task),
            dispatch=dispatch_out,
            subtask_id="test-task-001-S01",
            work_id="merge",
            out=impl_out,
        )
        # Merge using results_dir pattern (no explicit input_glob)
        merge_out = str(tmp_path / "implement_merge.json")
        rc = run_merge(
            work_id="merge",
            kind="implement",
            results_dir=str(tmp_path),
            dispatch=dispatch_out,
            out=merge_out,
        )
        # rc may be 0 or 2 depending on subtask matching; the key thing is
        # that the merge produced an output file with count/subtask_results
        assert rc in (0, 2)
        data = json.loads(open(merge_out, encoding="utf-8").read())
        assert "count" in data
        assert "subtask_results" in data

    def test_with_explicit_input_glob(self, sample_task, tmp_path):
        """Merge with explicit input_glob pattern."""
        setup_simulate_mode(True)
        dispatch_out = str(tmp_path / "dispatch_mg.json")
        run_split(task=str(sample_task), out=dispatch_out)
        impl_out = str(tmp_path / "implement_mg_test-task-001-S01.json")
        run_implement(
            task=str(sample_task),
            dispatch=dispatch_out,
            subtask_id="test-task-001-S01",
            work_id="mg",
            out=impl_out,
        )
        merge_out = str(tmp_path / "implement_mg.json")
        rc = run_merge(
            work_id="mg",
            kind="implement",
            input_glob=str(tmp_path / "implement_mg_*.json"),
            dispatch=dispatch_out,
            out=merge_out,
        )
        assert rc == 0

    def test_no_matching_files(self, tmp_path):
        """Merge with no matching result files should return non-zero."""
        merge_out = str(tmp_path / "implement_empty.json")
        rc = run_merge(
            work_id="empty",
            kind="implement",
            input_glob=str(tmp_path / "implement_empty_*.json"),
            out=merge_out,
        )
        # No results should produce blocked/failed status
        assert rc == 2


class TestRunVerify:
    def test_simulate_mode_with_commands(self, tmp_path):
        """Verify with explicit commands in simulate mode."""
        setup_simulate_mode(True)
        out = str(tmp_path / "verify.json")
        rc = run_verify(
            work_id="verify-test",
            platform="macos",
            out=out,
            commands='["echo ok"]',
        )
        assert rc == 0
        data = json.loads(open(out, encoding="utf-8").read())
        assert data["status"] == "passed"

    def test_no_commands_env_falls_back_to_config(self, tmp_path, monkeypatch):
        """Verify with no VERIFY_COMMANDS env var falls back to pipeline-config.json defaults."""
        monkeypatch.delenv("VERIFY_COMMANDS", raising=False)
        out = str(tmp_path / "verify_fallback.json")
        rc = run_verify(
            work_id="verify-fallback",
            platform="macos",
            out=out,
            commands="",
        )
        # pipeline-config.json has default_verify_commands, so verify should
        # proceed (rc depends on whether the default commands pass)
        assert rc in (0, 2)
        data = json.loads(open(out, encoding="utf-8").read())
        assert "status" in data
        assert "commands" in data


class TestRunReview:
    def _make_plan_and_implement(self, sample_task, tmp_path):
        """Helper to create plan, dispatch, implement, and verify result files."""
        setup_simulate_mode(True)
        plan_out = str(tmp_path / "plan_review.json")
        dispatch_out = str(tmp_path / "dispatch_review.json")
        run_plan(task=str(sample_task), work_id="review", out=plan_out)
        run_split(task=str(sample_task), plan=plan_out, out=dispatch_out)
        impl_sub_out = str(tmp_path / "implement_review_test-task-001-S01.json")
        run_implement(
            task=str(sample_task),
            dispatch=dispatch_out,
            subtask_id="test-task-001-S01",
            work_id="review",
            out=impl_sub_out,
        )
        impl_out = str(tmp_path / "implement_review.json")
        run_merge(
            work_id="review",
            kind="implement",
            results_dir=str(tmp_path),
            dispatch=dispatch_out,
            out=impl_out,
        )
        return plan_out, impl_out

    def test_with_single_string_verify(self, sample_task, tmp_path):
        """Review with a single verify path string."""
        plan_out, impl_out = self._make_plan_and_implement(sample_task, tmp_path)
        verify_out = str(tmp_path / "verify_review.json")
        run_verify(
            work_id="review", platform="macos", out=verify_out,
            commands='["echo ok"]',
        )
        review_out = str(tmp_path / "review_result.json")
        rc = run_review(
            work_id="review",
            plan=plan_out,
            implement=impl_out,
            verify=verify_out,
            out=review_out,
        )
        # rc can be 0 (ready_for_merge) or 2 (blocked) depending on stage results
        assert rc in (0, 2)
        data = json.loads(open(review_out, encoding="utf-8").read())
        assert "status" in data

    def test_with_list_verify(self, sample_task, tmp_path):
        """Review with a list of verify paths."""
        plan_out, impl_out = self._make_plan_and_implement(sample_task, tmp_path)
        verify_out = str(tmp_path / "verify_review.json")
        run_verify(
            work_id="review", platform="macos", out=verify_out,
            commands='["echo ok"]',
        )
        review_out = str(tmp_path / "review_list.json")
        rc = run_review(
            work_id="review",
            plan=plan_out,
            implement=impl_out,
            verify=[verify_out],
            out=review_out,
        )
        assert rc in (0, 2)

    def test_with_empty_verify(self, sample_task, tmp_path):
        """Review with empty string verify."""
        plan_out, impl_out = self._make_plan_and_implement(sample_task, tmp_path)
        review_out = str(tmp_path / "review_empty_verify.json")
        rc = run_review(
            work_id="review",
            plan=plan_out,
            implement=impl_out,
            verify="",
            out=review_out,
        )
        # Should still produce output (blocked likely)
        assert rc in (0, 2)
        data = json.loads(open(review_out, encoding="utf-8").read())
        assert "status" in data

    def test_with_none_verify(self, sample_task, tmp_path):
        """Review with None verify."""
        plan_out, impl_out = self._make_plan_and_implement(sample_task, tmp_path)
        review_out = str(tmp_path / "review_none_verify.json")
        rc = run_review(
            work_id="review",
            plan=plan_out,
            implement=impl_out,
            verify=None,
            out=review_out,
        )
        assert rc in (0, 2)
        data = json.loads(open(review_out, encoding="utf-8").read())
        assert "status" in data


class TestRunRetrospect:
    def test_simulate_mode(self, sample_task, tmp_path):
        """Retrospect produces output when given a valid review file."""
        setup_simulate_mode(True)
        # Build a minimal review file
        review_data = {
            "payload": {
                "work_id": "retro-test",
                "status": "ready_for_merge",
                "action_required": [],
                "open_questions": [],
                "go_no_go": False,
            }
        }
        review_path = tmp_path / "review_retro.json"
        review_path.write_text(json.dumps(review_data), encoding="utf-8")
        retro_out = str(tmp_path / "retrospect.json")
        rc = run_retrospect(
            work_id="retro-test",
            review=str(review_path),
            out=retro_out,
        )
        assert rc == 0
        data = json.loads(open(retro_out, encoding="utf-8").read())
        assert data["status"] == "ready"
        assert "next_plan" in data

    def test_missing_review_file(self, tmp_path):
        """Retrospect with missing review file should fail."""
        retro_out = str(tmp_path / "retrospect.json")
        rc = run_retrospect(
            work_id="retro-missing",
            review=str(tmp_path / "nonexistent_review.json"),
            out=retro_out,
        )
        assert rc == 1

    def test_with_action_required(self, tmp_path):
        """Retrospect generates rework next_plan items from action_required."""
        review_data = {
            "payload": {
                "work_id": "retro-action",
                "status": "blocked",
                "action_required": [
                    "Implementation status is 'failed'.",
                    "Verify status is 'failed' on macos.",
                ],
                "open_questions": ["Some open question"],
                "go_no_go": True,
            }
        }
        review_path = tmp_path / "review_action.json"
        review_path.write_text(json.dumps(review_data), encoding="utf-8")
        retro_out = str(tmp_path / "retrospect_action.json")
        rc = run_retrospect(
            work_id="retro-action",
            review=str(review_path),
            out=retro_out,
        )
        assert rc == 0
        data = json.loads(open(retro_out, encoding="utf-8").read())
        assert len(data["next_plan"]) >= 2
        assert data["next_plan"][0]["type"] == "rework"
