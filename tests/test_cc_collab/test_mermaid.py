"""Tests for Mermaid pipeline visualization."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cc_collab.web.mermaid import (
    PIPELINE_STAGES,
    STAGE_LABELS,
    _status_class,
    generate_pipeline_diagram,
    generate_pipeline_diagram_from_results,
    generate_pipeline_diagram_from_stages,
)


class TestStatusClass:
    def test_completed_aliases(self):
        for s in ("completed", "passed", "ready", "done"):
            assert _status_class(s) == "completed"

    def test_running(self):
        assert _status_class("running") == "running"

    def test_failed(self):
        assert _status_class("failed") == "failed"

    def test_skipped(self):
        assert _status_class("skipped") == "skipped"

    def test_unknown_defaults_to_pending(self):
        assert _status_class("unknown") == "pending"
        assert _status_class("") == "pending"


class TestGenerateDiagram:
    def test_empty_statuses(self):
        diagram = generate_pipeline_diagram({})
        assert "graph TD" in diagram
        for stage in PIPELINE_STAGES:
            assert stage in diagram

    def test_all_completed(self):
        statuses = {s: "completed" for s in PIPELINE_STAGES}
        diagram = generate_pipeline_diagram(statuses)
        assert ":::completed" in diagram
        assert ":::pending" not in diagram

    def test_mixed_statuses(self):
        statuses = {
            "validate": "completed",
            "plan": "completed",
            "split": "running",
        }
        diagram = generate_pipeline_diagram(statuses)
        assert ":::completed" in diagram
        assert ":::running" in diagram
        assert ":::pending" in diagram

    def test_failed_stage(self):
        statuses = {"validate": "completed", "plan": "failed"}
        diagram = generate_pipeline_diagram(statuses)
        assert ":::failed" in diagram

    def test_sequential_edges(self):
        diagram = generate_pipeline_diagram({})
        assert "validate --> plan" in diagram
        assert "plan --> split" in diagram
        assert "split --> implement" in diagram
        assert "verify --> review" in diagram

    def test_stage_labels_present(self):
        diagram = generate_pipeline_diagram({})
        for label in STAGE_LABELS.values():
            assert label in diagram

    def test_with_subtasks(self):
        statuses = {
            "validate": "completed",
            "implement": "completed",
        }
        diagram = generate_pipeline_diagram(statuses, subtask_ids=["S01", "S02"])
        assert "S01" in diagram
        assert "S02" in diagram
        assert "sub0" in diagram
        assert "sub1" in diagram

    def test_classdefs_present(self):
        diagram = generate_pipeline_diagram({})
        assert "classDef completed" in diagram
        assert "classDef running" in diagram
        assert "classDef failed" in diagram
        assert "classDef pending" in diagram


class TestFromStages:
    def test_with_stage_objects(self):
        class MockStage:
            def __init__(self, name, status):
                self.stage_name = name
                self.status = status

        stages = [MockStage("validate", "completed"), MockStage("plan", "running")]
        diagram = generate_pipeline_diagram_from_stages(stages)
        assert "graph TD" in diagram
        assert ":::completed" in diagram
        assert ":::running" in diagram

    def test_with_dicts(self):
        stages = [
            {"stage_name": "validate", "status": "passed"},
            {"stage_name": "plan", "status": "failed"},
        ]
        diagram = generate_pipeline_diagram_from_stages(stages)
        assert ":::completed" in diagram
        assert ":::failed" in diagram

    def test_empty_list(self):
        diagram = generate_pipeline_diagram_from_stages([])
        assert "graph TD" in diagram


class TestFromResults:
    def test_with_result_files(self, tmp_path):
        work_id = "test123"
        (tmp_path / f"validation_{work_id}.json").write_text(
            json.dumps({"status": "ready"}), encoding="utf-8"
        )
        (tmp_path / f"plan_{work_id}.json").write_text(
            json.dumps({"status": "completed"}), encoding="utf-8"
        )
        diagram = generate_pipeline_diagram_from_results(work_id, str(tmp_path))
        assert ":::completed" in diagram

    def test_nonexistent_dir(self):
        diagram = generate_pipeline_diagram_from_results("xyz", "/nonexistent/path")
        assert "graph TD" in diagram

    def test_subtask_files(self, tmp_path):
        work_id = "sub123"
        (tmp_path / f"implement_{work_id}_S01.json").write_text(
            json.dumps({"status": "passed"}), encoding="utf-8"
        )
        (tmp_path / f"implement_{work_id}_S02.json").write_text(
            json.dumps({"status": "failed"}), encoding="utf-8"
        )
        diagram = generate_pipeline_diagram_from_results(work_id, str(tmp_path))
        assert "S01" in diagram
        assert "S02" in diagram
