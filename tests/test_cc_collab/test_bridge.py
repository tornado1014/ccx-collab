"""Tests for cc_collab.bridge module."""

from __future__ import annotations

import os
import pytest

from cc_collab.bridge import (
    run_health_check,
    run_validate,
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
        import json
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
        import json
        result = json.loads(open(out, encoding="utf-8").read())
        assert result["status"] == "skipped"
