"""Comprehensive unit tests for orchestrate.py (target >= 80% coverage)."""

import argparse
import hashlib
import json
import os
import pathlib
import sys
from unittest import mock

import pytest

# Import orchestrate via sys.path manipulation
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import orchestrate


# ---------------------------------------------------------------------------
# 1. normalize_task
# ---------------------------------------------------------------------------

class TestNormalizeTask:
    def test_valid_task(self, sample_task):
        normalized, errors = orchestrate.normalize_task(sample_task)
        assert not errors
        assert normalized["task_id"] == "test-task-001"
        assert len(normalized["subtasks"]) == 1

    def test_missing_fields(self):
        task = {}
        normalized, errors = orchestrate.normalize_task(task)
        assert "missing task_id" in errors
        assert "missing title" in errors
        assert "missing scope" in errors
        assert "missing risk_level" in errors
        assert "missing priority" in errors
        assert normalized["task_id"] == "task-unknown"

    def test_empty_subtasks_generates_default(self):
        task = {
            "task_id": "t1",
            "title": "Test",
            "scope": "testing",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": ["AC1"],
            "subtasks": [],
        }
        normalized, errors = orchestrate.normalize_task(task)
        assert len(normalized["subtasks"]) == 1
        assert normalized["subtasks"][0]["subtask_id"] == "t1-S01"

    def test_string_subtasks(self):
        task = {
            "task_id": "t2",
            "title": "Test",
            "scope": "testing",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": ["AC1"],
            "subtasks": ["Do something", "Do another"],
        }
        normalized, errors = orchestrate.normalize_task(task)
        assert len(normalized["subtasks"]) == 2
        assert normalized["subtasks"][0]["title"] == "Do something"
        assert normalized["subtasks"][1]["subtask_id"] == "t2-S02"

    def test_dict_subtask_as_single(self):
        task = {
            "task_id": "t3",
            "title": "Test",
            "scope": "testing",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": ["AC1"],
            "subtasks": {"subtask_id": "t3-S01", "title": "Only one"},
        }
        normalized, errors = orchestrate.normalize_task(task)
        assert "subtasks should be an array" in errors
        assert len(normalized["subtasks"]) == 1

    def test_invalid_subtask_type_skipped(self):
        task = {
            "task_id": "t4",
            "title": "Test",
            "scope": "testing",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": ["AC1"],
            "subtasks": [42],
        }
        normalized, errors = orchestrate.normalize_task(task)
        assert any("must be object or string" in e for e in errors)
        # fallback generates default since no valid subtask was parsed
        assert len(normalized["subtasks"]) == 1

    def test_acceptance_criteria_not_list(self):
        task = {
            "task_id": "t5",
            "title": "T",
            "scope": "s",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": "not a list",
        }
        normalized, errors = orchestrate.normalize_task(task)
        assert "acceptance_criteria must be a non-empty array" in errors

    def test_platform_normalization(self):
        task = {
            "task_id": "t6",
            "title": "T",
            "scope": "s",
            "risk_level": "low",
            "priority": "high",
            "acceptance_criteria": ["AC"],
            "platform": "mac,windows",
            "subtasks": [],
        }
        normalized, _ = orchestrate.normalize_task(task)
        assert "mac" in normalized["platform"]
        assert "windows" in normalized["platform"]


# ---------------------------------------------------------------------------
# 2. normalize_subtask_role
# ---------------------------------------------------------------------------

class TestNormalizeSubtaskRole:
    def test_role_architect(self):
        assert orchestrate.normalize_subtask_role({"role": "architect"}) == "architect"

    def test_role_builder(self):
        assert orchestrate.normalize_subtask_role({"role": "builder"}) == "builder"

    def test_owner_claude(self):
        assert orchestrate.normalize_subtask_role({"owner": "claude"}) == "architect"

    def test_owner_codex(self):
        assert orchestrate.normalize_subtask_role({"owner": "codex"}) == "builder"

    def test_default_builder(self):
        assert orchestrate.normalize_subtask_role({}) == "builder"

    def test_invalid_role_falls_to_owner(self):
        assert orchestrate.normalize_subtask_role({"role": "unknown", "owner": "claude"}) == "architect"


# ---------------------------------------------------------------------------
# 3. normalize_platform
# ---------------------------------------------------------------------------

class TestNormalizePlatform:
    def test_string(self):
        assert orchestrate.normalize_platform("mac") == ["mac"]

    def test_comma_separated(self):
        assert orchestrate.normalize_platform("mac, windows") == ["mac", "windows"]

    def test_list(self):
        assert orchestrate.normalize_platform(["mac", "windows"]) == ["mac", "windows"]

    def test_none(self):
        assert orchestrate.normalize_platform(None) == ["both"]

    def test_invalid_type(self):
        assert orchestrate.normalize_platform(42) == ["both"]

    def test_empty_string(self):
        # empty string splits to no valid tokens, returns empty list
        assert orchestrate.normalize_platform("") == []


# ---------------------------------------------------------------------------
# 4. parse_verify_commands
# ---------------------------------------------------------------------------

class TestParseVerifyCommands:
    def test_json_array(self):
        result = orchestrate.parse_verify_commands('["pytest", "flake8"]')
        assert result == ["pytest", "flake8"]

    def test_semicolons(self):
        result = orchestrate.parse_verify_commands("pytest;flake8")
        assert result == ["pytest", "flake8"]

    def test_newlines(self):
        result = orchestrate.parse_verify_commands("pytest\nflake8")
        assert result == ["pytest", "flake8"]

    def test_empty(self):
        assert orchestrate.parse_verify_commands("") == []

    def test_whitespace_only(self):
        assert orchestrate.parse_verify_commands("   ") == []

    def test_json_array_with_empty_strings(self):
        result = orchestrate.parse_verify_commands('["pytest", "", "flake8"]')
        assert result == ["pytest", "flake8"]


# ---------------------------------------------------------------------------
# 5. parse_cli_envelope
# ---------------------------------------------------------------------------

class TestParseCliEnvelope:
    def test_valid_envelope_with_nested_stdout(self):
        envelope = {
            "status": "passed",
            "stdout": json.dumps({"result": {"files": ["a.py"]}}),
        }
        parsed = orchestrate.parse_cli_envelope(json.dumps(envelope))
        assert parsed["envelope"]["status"] == "passed"
        assert parsed["result"] == {"files": ["a.py"]}

    def test_valid_envelope_no_nested(self):
        envelope = {"status": "passed", "stdout": "not json", "result": {"ok": True}}
        parsed = orchestrate.parse_cli_envelope(json.dumps(envelope))
        assert parsed["result"] == {"ok": True}

    def test_plain_dict_no_status_stdout(self):
        data = {"result": {"hello": "world"}}
        parsed = orchestrate.parse_cli_envelope(json.dumps(data))
        assert parsed["result"] == {"hello": "world"}

    def test_invalid_json(self):
        parsed = orchestrate.parse_cli_envelope("not valid json at all")
        assert parsed["envelope"]["status"] == "failed"
        assert parsed["result"] == {}

    def test_empty_string(self):
        parsed = orchestrate.parse_cli_envelope("")
        assert parsed["envelope"]["status"] == "failed"

    def test_json_list_returns_failed(self):
        parsed = orchestrate.parse_cli_envelope("[1, 2, 3]")
        assert parsed["envelope"]["status"] == "failed"


# ---------------------------------------------------------------------------
# 6. build_report_status
# ---------------------------------------------------------------------------

class TestBuildReportStatus:
    def test_failed(self):
        assert orchestrate.build_report_status(["passed", "failed"]) == "failed"

    def test_skipped(self):
        assert orchestrate.build_report_status(["passed", "skipped"]) == "failed"

    def test_blocked(self):
        assert orchestrate.build_report_status(["blocked"]) == "blocked"

    def test_simulated(self):
        assert orchestrate.build_report_status(["simulated"]) == "done"

    def test_passed(self):
        assert orchestrate.build_report_status(["passed"]) == "done"

    def test_ready(self):
        assert orchestrate.build_report_status(["ready"]) == "ready"

    def test_empty_returns_done(self):
        assert orchestrate.build_report_status([]) == "done"

    def test_priority_failed_over_blocked(self):
        assert orchestrate.build_report_status(["blocked", "failed"]) == "failed"


# ---------------------------------------------------------------------------
# 7. action_validate_task
# ---------------------------------------------------------------------------

class TestActionValidateTask:
    def test_valid_task(self, sample_task_file, tmp_results_dir):
        out_path = tmp_results_dir / "validation.json"
        args = argparse.Namespace(
            task=str(sample_task_file),
            work_id="test-wid",
            out=str(out_path),
        )
        rc = orchestrate.action_validate_task(args)
        assert rc == 0
        result = json.loads(out_path.read_text())
        assert result["status"] == "ready"

    def test_invalid_task(self, tmp_path, tmp_results_dir):
        task_file = tmp_path / "bad-task.json"
        task_file.write_text(json.dumps({"subtasks": []}))
        out_path = tmp_results_dir / "validation_bad.json"
        args = argparse.Namespace(
            task=str(task_file),
            work_id="bad-wid",
            out=str(out_path),
        )
        rc = orchestrate.action_validate_task(args)
        assert rc == 2
        result = json.loads(out_path.read_text())
        assert result["status"] == "blocked"
        assert len(result["validation_errors"]) > 0


# ---------------------------------------------------------------------------
# 8. action_split_task
# ---------------------------------------------------------------------------

class TestActionSplitTask:
    def test_basic_split(self, sample_task_file, tmp_results_dir):
        out_path = tmp_results_dir / "split.json"
        args = argparse.Namespace(
            task=str(sample_task_file),
            plan="",
            out=str(out_path),
            matrix_output="",
        )
        rc = orchestrate.action_split_task(args)
        assert rc == 0
        result = json.loads(out_path.read_text())
        assert result["status"] == "done"
        assert len(result["subtasks"]) >= 1

    def test_split_with_plan_chunks(self, sample_task_file, tmp_path, tmp_results_dir):
        plan_data = {
            "chunks": [
                {
                    "chunk_id": "C01",
                    "title": "Chunk 1",
                    "role": "architect",
                    "scope": "planning",
                    "estimated_minutes": 45,
                    "depends_on": [],
                    "files_affected": [],
                    "acceptance_criteria": [],
                }
            ]
        }
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data))
        out_path = tmp_results_dir / "split_plan.json"
        args = argparse.Namespace(
            task=str(sample_task_file),
            plan=str(plan_file),
            out=str(out_path),
            matrix_output="",
        )
        rc = orchestrate.action_split_task(args)
        assert rc == 0
        result = json.loads(out_path.read_text())
        assert result["subtasks"][0]["subtask_id"] == "C01"
        assert result["subtasks"][0]["role"] == "architect"

    def test_split_with_matrix_output(self, sample_task_file, tmp_results_dir):
        out_path = tmp_results_dir / "split_m.json"
        matrix_path = tmp_results_dir / "matrix.json"
        args = argparse.Namespace(
            task=str(sample_task_file),
            plan="",
            out=str(out_path),
            matrix_output=str(matrix_path),
        )
        rc = orchestrate.action_split_task(args)
        assert rc == 0
        assert matrix_path.exists()
        matrix = json.loads(matrix_path.read_text())
        assert isinstance(matrix, list)
        assert len(matrix) >= 1


# ---------------------------------------------------------------------------
# 9. sha256_bytes / sha256_file
# ---------------------------------------------------------------------------

class TestSha256:
    def test_sha256_bytes(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert orchestrate.sha256_bytes(data) == expected

    def test_sha256_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"test content")
        expected = hashlib.sha256(b"test content").hexdigest()
        assert orchestrate.sha256_file(f) == expected


# ---------------------------------------------------------------------------
# 10. normalize_acceptance_criteria
# ---------------------------------------------------------------------------

class TestNormalizeAcceptanceCriteria:
    def test_string_items(self):
        raw = ["Tests pass", "No warnings"]
        result = orchestrate.normalize_acceptance_criteria(raw, "S01")
        assert len(result) == 2
        assert result[0]["id"] == "AC-S01-1"
        assert result[0]["description"] == "Tests pass"
        assert result[0]["category"] == "functional"

    def test_dict_items(self):
        raw = [
            {
                "id": "AC-01",
                "description": "Check output",
                "verification": "pytest -v",
                "verify_pattern": "PASSED",
                "category": "integration",
            }
        ]
        result = orchestrate.normalize_acceptance_criteria(raw, "S01")
        assert len(result) == 1
        assert result[0]["id"] == "AC-01"
        assert result[0]["verify_command"] == "pytest -v"
        assert result[0]["category"] == "integration"

    def test_mixed_items(self):
        raw = [
            "String criterion",
            {"id": "AC-02", "verification": "echo ok", "description": "Dict criterion"},
        ]
        result = orchestrate.normalize_acceptance_criteria(raw, "S02")
        assert len(result) == 2
        assert result[0]["id"] == "AC-S02-1"
        assert result[1]["id"] == "AC-02"


# ---------------------------------------------------------------------------
# 11. build_chunks_from_subtasks
# ---------------------------------------------------------------------------

class TestBuildChunksFromSubtasks:
    def test_normal_subtask(self):
        task = {
            "task_id": "T1",
            "subtasks": [
                {
                    "subtask_id": "S01",
                    "title": "Small task",
                    "estimated_minutes": 60,
                    "acceptance_criteria": ["AC1"],
                }
            ],
        }
        chunks = orchestrate.build_chunks_from_subtasks(task, {})
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "T1-C01"
        assert chunks[0]["estimated_minutes"] == 60

    def test_over_90min_split(self):
        task = {
            "task_id": "T2",
            "subtasks": [
                {
                    "subtask_id": "S01",
                    "title": "Big task",
                    "estimated_minutes": 180,
                    "acceptance_criteria": ["AC1", "AC2", "AC3", "AC4"],
                }
            ],
        }
        chunks = orchestrate.build_chunks_from_subtasks(task, {})
        assert len(chunks) == 2
        assert "part 1" in chunks[0]["title"]
        assert "part 2" in chunks[1]["title"]

    def test_plan_data_chunks_used_directly(self):
        task = {"task_id": "T3", "subtasks": []}
        plan_data = {
            "chunks": [
                {"chunk_id": "prebuilt-C01", "title": "Pre-built chunk"}
            ]
        }
        chunks = orchestrate.build_chunks_from_subtasks(task, plan_data)
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "prebuilt-C01"

    def test_under_30min_clamped(self):
        task = {
            "task_id": "T4",
            "subtasks": [
                {
                    "subtask_id": "S01",
                    "title": "Tiny task",
                    "estimated_minutes": 10,
                    "acceptance_criteria": [],
                }
            ],
        }
        chunks = orchestrate.build_chunks_from_subtasks(task, {})
        assert chunks[0]["estimated_minutes"] == 30


# ---------------------------------------------------------------------------
# 12. write_with_meta
# ---------------------------------------------------------------------------

class TestWriteWithMeta:
    def test_output_structure(self, tmp_results_dir):
        out = tmp_results_dir / "meta_test.json"
        payload = {"status": "done", "data": [1, 2, 3]}
        result = orchestrate.write_with_meta("test-agent", "wid-001", payload, out)
        assert out.exists()
        written = json.loads(out.read_text())
        assert written["agent"] == "test-agent"
        assert written["work_id"] == "wid-001"
        assert "generated_at" in written
        assert "checksum" in written
        assert written["status"] == "done"
        assert written["data"] == [1, 2, 3]

    def test_checksum_deterministic(self, tmp_results_dir):
        out1 = tmp_results_dir / "meta_1.json"
        out2 = tmp_results_dir / "meta_2.json"
        payload = {"a": 1}
        r1 = orchestrate.write_with_meta("ag", "w1", payload, out1)
        r2 = orchestrate.write_with_meta("ag", "w1", payload, out2)
        assert r1["checksum"] == r2["checksum"]


# ---------------------------------------------------------------------------
# 13. as_payload
# ---------------------------------------------------------------------------

class TestAsPayload:
    def test_with_payload_wrapper(self):
        node = {"payload": {"status": "done", "data": 42}}
        assert orchestrate.as_payload(node) == {"status": "done", "data": 42}

    def test_without_payload_wrapper(self):
        node = {"status": "done", "data": 42}
        assert orchestrate.as_payload(node) == node

    def test_payload_not_dict(self):
        node = {"payload": "string-value"}
        assert orchestrate.as_payload(node) == node


# ---------------------------------------------------------------------------
# Extra: now_iso, ensure_parent, load_json, write_json, command_output_trace
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_now_iso_format(self):
        ts = orchestrate.now_iso()
        assert ts.endswith("Z")
        assert "T" in ts

    def test_ensure_parent(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "file.txt"
        orchestrate.ensure_parent(nested)
        assert nested.parent.exists()

    def test_load_and_write_json(self, tmp_path):
        f = tmp_path / "rw.json"
        data = {"key": "value", "num": 42}
        orchestrate.write_json(f, data)
        loaded = orchestrate.load_json(f)
        assert loaded == data

    def test_command_output_trace_short(self):
        assert orchestrate.command_output_trace("short") == "short"

    def test_command_output_trace_long(self):
        long_cmd = "x" * 200
        result = orchestrate.command_output_trace(long_cmd)
        assert result.endswith("...")
        assert len(result) == 183  # 180 + "..."


# ---------------------------------------------------------------------------
# 14. run_agent_command - simulation mode
# ---------------------------------------------------------------------------

class TestRunAgentCommand:
    def test_simulation_mode_no_command(self):
        with mock.patch.dict(os.environ, {"SIMULATE_AGENTS": "1"}):
            result = orchestrate.run_agent_command("claude", "", {"task": "test"})
            assert result["status"] == "simulated"
            assert result["return_code"] == 0
            assert "simulation" in result["stdout"]

    def test_no_command_no_simulation_raises(self):
        with mock.patch.dict(os.environ, {"SIMULATE_AGENTS": "0"}, clear=False):
            with pytest.raises(RuntimeError, match="CLI command not configured"):
                orchestrate.run_agent_command("claude", "", {"task": "test"})

    def test_successful_command(self):
        with mock.patch.dict(os.environ, {"AGENT_MAX_RETRIES": "1", "AGENT_RETRY_SLEEP": "0"}):
            result = orchestrate.run_agent_command("claude", "echo hello", {"task": "test"})
            assert result["status"] == "passed"
            assert result["return_code"] == 0
            assert "payload_checksum" in result

    def test_failed_command_retries(self):
        with mock.patch.dict(os.environ, {"AGENT_MAX_RETRIES": "2", "AGENT_RETRY_SLEEP": "0"}):
            result = orchestrate.run_agent_command("codex", "/bin/sh -c 'exit 1'", {"task": "test"})
            assert result["status"] == "failed"
            assert result["attempt"] == 2


# ---------------------------------------------------------------------------
# 15. acquire_lock / release_lock
# ---------------------------------------------------------------------------

class TestFileLock:
    def test_acquire_and_release(self, tmp_path):
        lock_target = tmp_path / "test_file.json"
        fd = orchestrate.acquire_lock(lock_target)
        assert fd is not None
        orchestrate.release_lock(fd)

    def test_release_lock_no_error_on_none(self):
        # release_lock should handle already-closed fd gracefully
        class FakeFd:
            def close(self):
                raise OSError("already closed")
        orchestrate.release_lock(FakeFd())  # should not raise


# ---------------------------------------------------------------------------
# 16. build_junit_xml
# ---------------------------------------------------------------------------

class TestBuildJunitXml:
    def test_basic_junit(self, tmp_results_dir):
        test_results = [
            {"status": "passed", "command": "pytest", "time_ms": 1200},
            {"status": "failed", "command": "flake8", "time_ms": 300},
        ]
        junit_path = tmp_results_dir / "junit_test.xml"
        orchestrate.build_junit_xml(test_results, "test-suite", junit_path, 1.5, 1)
        assert junit_path.exists()
        content = junit_path.read_text()
        assert 'name="test-suite"' in content
        assert 'tests="2"' in content
        assert 'failures="1"' in content
        assert "<failure" in content

    def test_all_passed(self, tmp_results_dir):
        test_results = [
            {"status": "passed", "command": "pytest", "time_ms": 500},
        ]
        junit_path = tmp_results_dir / "junit_pass.xml"
        orchestrate.build_junit_xml(test_results, "pass-suite", junit_path, 0.5, 0)
        content = junit_path.read_text()
        assert 'failures="0"' in content
        assert "<failure" not in content


# ---------------------------------------------------------------------------
# 17. action_review
# ---------------------------------------------------------------------------

class TestActionReview:
    def _write_phase(self, path, payload):
        orchestrate.write_json(path, payload)

    def test_all_phases_pass(self, tmp_path, tmp_results_dir):
        plan = tmp_path / "plan.json"
        impl = tmp_path / "impl.json"
        verify = tmp_path / "verify.json"
        out = tmp_results_dir / "review.json"

        self._write_phase(plan, {"status": "done"})
        self._write_phase(impl, {"status": "done"})
        self._write_phase(verify, {"status": "passed", "platform": "mac"})

        args = argparse.Namespace(
            work_id="rev-001",
            plan=str(plan),
            implement=str(impl),
            verify=[str(verify)],
            out=str(out),
        )
        rc = orchestrate.action_review(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "ready_for_merge"
        assert result["go_no_go"] is False

    def test_plan_not_done_blocks(self, tmp_path, tmp_results_dir):
        plan = tmp_path / "plan.json"
        impl = tmp_path / "impl.json"
        out = tmp_results_dir / "review_blocked.json"

        self._write_phase(plan, {"status": "blocked"})
        self._write_phase(impl, {"status": "done"})

        args = argparse.Namespace(
            work_id="rev-002",
            plan=str(plan),
            implement=str(impl),
            verify=[],
            out=str(out),
        )
        rc = orchestrate.action_review(args)
        assert rc == 2
        result = json.loads(out.read_text())
        assert result["status"] == "blocked"
        assert result["go_no_go"] is True

    def test_verify_failed_blocks(self, tmp_path, tmp_results_dir):
        plan = tmp_path / "plan.json"
        impl = tmp_path / "impl.json"
        verify = tmp_path / "verify.json"
        out = tmp_results_dir / "review_vfail.json"

        self._write_phase(plan, {"status": "done"})
        self._write_phase(impl, {"status": "done"})
        self._write_phase(verify, {"status": "failed", "platform": "mac"})

        args = argparse.Namespace(
            work_id="rev-003",
            plan=str(plan),
            implement=str(impl),
            verify=[str(verify)],
            out=str(out),
        )
        rc = orchestrate.action_review(args)
        assert rc == 2

    def test_impl_not_done_blocks(self, tmp_path, tmp_results_dir):
        plan = tmp_path / "plan.json"
        impl = tmp_path / "impl.json"
        out = tmp_results_dir / "review_impl.json"

        self._write_phase(plan, {"status": "done"})
        self._write_phase(impl, {"status": "failed"})

        args = argparse.Namespace(
            work_id="rev-004",
            plan=str(plan),
            implement=str(impl),
            verify=[],
            out=str(out),
        )
        rc = orchestrate.action_review(args)
        assert rc == 2


# ---------------------------------------------------------------------------
# 18. action_retrospect
# ---------------------------------------------------------------------------

class TestActionRetrospect:
    def test_basic_retrospect(self, tmp_path, tmp_results_dir):
        review_file = tmp_path / "review.json"
        orchestrate.write_json(review_file, {
            "action_required": ["Fix test", "Update docs"],
            "open_questions": ["Why is CI slow?"],
            "go_no_go": True,
        })
        out = tmp_results_dir / "retro.json"
        args = argparse.Namespace(
            work_id="retro-001",
            review=str(review_file),
            out=str(out),
        )
        rc = orchestrate.action_retrospect(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "ready"
        assert len(result["next_plan"]) >= 1

    def test_no_issues_retrospect(self, tmp_path, tmp_results_dir):
        review_file = tmp_path / "review_ok.json"
        orchestrate.write_json(review_file, {
            "action_required": [],
            "open_questions": [],
            "go_no_go": False,
        })
        out = tmp_results_dir / "retro_ok.json"
        args = argparse.Namespace(
            work_id="retro-002",
            review=str(review_file),
            out=str(out),
        )
        rc = orchestrate.action_retrospect(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["next_plan"][0]["type"] == "observe"

    def test_missing_review_returns_1(self, tmp_path, tmp_results_dir):
        out = tmp_results_dir / "retro_miss.json"
        args = argparse.Namespace(
            work_id="retro-003",
            review=str(tmp_path / "nonexistent.json"),
            out=str(out),
        )
        rc = orchestrate.action_retrospect(args)
        assert rc == 1


# ---------------------------------------------------------------------------
# 19. action_merge_results
# ---------------------------------------------------------------------------

class TestActionMergeResults:
    def test_merge_single_result(self, tmp_path, tmp_results_dir):
        impl_file = tmp_path / "impl_S01.json"
        orchestrate.write_json(impl_file, {
            "status": "done",
            "subtask": {"subtask_id": "S01"},
            "files_changed": ["a.py"],
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
            "open_questions": [],
        })
        out = tmp_results_dir / "merged.json"
        args = argparse.Namespace(
            work_id="merge-001",
            kind="implement",
            input=str(impl_file),
            out=str(out),
            dispatch="",
        )
        rc = orchestrate.action_merge_results(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "done"
        assert result["count"] == 1

    def test_merge_no_results(self, tmp_path, tmp_results_dir):
        out = tmp_results_dir / "merged_empty.json"
        args = argparse.Namespace(
            work_id="merge-002",
            kind="implement",
            input=str(tmp_path / "nonexistent.json"),
            out=str(out),
            dispatch="",
        )
        rc = orchestrate.action_merge_results(args)
        assert rc == 2
        result = json.loads(out.read_text())
        assert result["status"] == "blocked"

    def test_merge_with_glob(self, tmp_path, tmp_results_dir):
        for i in range(3):
            f = tmp_path / f"impl_{i}.json"
            orchestrate.write_json(f, {
                "status": "done",
                "subtask": {"subtask_id": f"S{i:02d}"},
                "files_changed": [f"file{i}.py"],
                "commands_executed": [],
                "failed_tests": [],
                "artifacts": [],
                "open_questions": [],
            })
        out = tmp_results_dir / "merged_glob.json"
        args = argparse.Namespace(
            work_id="merge-003",
            kind="implement",
            input=str(tmp_path / "impl_*.json"),
            out=str(out),
            dispatch="",
        )
        rc = orchestrate.action_merge_results(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["count"] == 3

    def test_merge_with_dispatch_missing_subtask(self, tmp_path, tmp_results_dir):
        dispatch_file = tmp_path / "dispatch.json"
        orchestrate.write_json(dispatch_file, {
            "subtasks": [
                {"subtask_id": "S01"},
                {"subtask_id": "S02"},
            ]
        })
        impl_file = tmp_path / "impl_S01.json"
        orchestrate.write_json(impl_file, {
            "status": "done",
            "subtask": {"subtask_id": "S01"},
            "files_changed": [],
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
            "open_questions": [],
        })
        out = tmp_results_dir / "merged_missing.json"
        args = argparse.Namespace(
            work_id="merge-004",
            kind="implement",
            input=str(impl_file),
            out=str(out),
            dispatch=str(dispatch_file),
        )
        rc = orchestrate.action_merge_results(args)
        assert rc == 2
        result = json.loads(out.read_text())
        assert "S02" in result["missing_subtasks"]


# ---------------------------------------------------------------------------
# 20. action_run_verify (with simple echo commands)
# ---------------------------------------------------------------------------

class TestActionRunVerify:
    def test_verify_passes(self, tmp_results_dir):
        out = tmp_results_dir / "verify.json"
        args = argparse.Namespace(
            work_id="verify-001",
            platform="mac",
            out=str(out),
            commands='["echo pass"]',
        )
        with mock.patch.dict(os.environ, {"VERIFY_COMMANDS": '["echo pass"]'}):
            rc = orchestrate.action_run_verify(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "passed"

    def test_verify_fails(self, tmp_results_dir):
        out = tmp_results_dir / "verify_fail.json"
        args = argparse.Namespace(
            work_id="verify-002",
            platform="mac",
            out=str(out),
            commands='["/bin/sh -c \'exit 1\'"]',
        )
        with mock.patch.dict(os.environ, {"VERIFY_COMMANDS": '["/bin/sh -c \'exit 1\'"]'}):
            rc = orchestrate.action_run_verify(args)
        assert rc == 2
        result = json.loads(out.read_text())
        assert result["status"] == "failed"

    def test_verify_no_commands(self, tmp_results_dir):
        out = tmp_results_dir / "verify_none.json"
        args = argparse.Namespace(
            work_id="verify-003",
            platform="mac",
            out=str(out),
            commands="",
        )
        # Mock ROOT to a temp dir so pipeline-config.json fallback doesn't find real commands
        fake_root = tmp_results_dir / "fake_root"
        fake_root.mkdir(exist_ok=True)
        with mock.patch.dict(os.environ, {"VERIFY_COMMANDS": ""}, clear=False), \
             mock.patch.object(orchestrate, "ROOT", fake_root):
            rc = orchestrate.action_run_verify(args)
        assert rc == 1
        result = json.loads(out.read_text())
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# 21. action_run_plan (simulation)
# ---------------------------------------------------------------------------

class TestActionRunPlan:
    def test_run_plan_simulation(self, sample_task_file, tmp_results_dir):
        out = tmp_results_dir / "plan.json"
        with mock.patch.dict(os.environ, {
            "SIMULATE_AGENTS": "1",
            "CLAUDE_CODE_CMD": "",
        }):
            args = argparse.Namespace(
                task=str(sample_task_file),
                work_id="plan-001",
                out=str(out),
            )
            rc = orchestrate.action_run_plan(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "done"


# ---------------------------------------------------------------------------
# 22. action_run_implement (simulation)
# ---------------------------------------------------------------------------

class TestActionRunImplement:
    def test_implement_simulation(self, sample_task_file, tmp_results_dir):
        out = tmp_results_dir / "impl.json"
        with mock.patch.dict(os.environ, {
            "SIMULATE_AGENTS": "1",
            "CODEX_CLI_CMD": "",
        }):
            args = argparse.Namespace(
                task=str(sample_task_file),
                dispatch="",
                subtask_id="test-task-001-S01",
                work_id="impl-001",
                out=str(out),
            )
            rc = orchestrate.action_run_implement(args)
        assert rc == 0
        result = json.loads(out.read_text())
        assert result["status"] == "done"

    def test_implement_missing_subtask(self, sample_task_file, tmp_results_dir):
        out = tmp_results_dir / "impl_miss.json"
        with mock.patch.dict(os.environ, {"SIMULATE_AGENTS": "1", "CODEX_CLI_CMD": ""}):
            args = argparse.Namespace(
                task=str(sample_task_file),
                dispatch="",
                subtask_id="nonexistent-subtask",
                work_id="impl-002",
                out=str(out),
            )
            rc = orchestrate.action_run_implement(args)
        assert rc == 1


# ---------------------------------------------------------------------------
# 23. build_parser / main
# ---------------------------------------------------------------------------

class TestBuildParserAndMain:
    def test_build_parser_returns_parser(self):
        parser = orchestrate.build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_main_no_args(self):
        with mock.patch("sys.argv", ["orchestrate.py"]):
            rc = orchestrate.main()
        assert rc == 1

    def test_main_validate_task(self, sample_task_file, tmp_results_dir):
        out = tmp_results_dir / "main_validate.json"
        with mock.patch("sys.argv", [
            "orchestrate.py", "validate-task",
            "--task", str(sample_task_file),
            "--out", str(out),
        ]):
            rc = orchestrate.main()
        assert rc == 0
