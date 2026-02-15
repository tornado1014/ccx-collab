"""Schema validation tests for all JSON schemas in agent/schemas/."""

import json
import pathlib

import jsonschema
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parents[1] / "schemas"


def load_schema(name: str) -> dict:
    """Load a JSON schema by filename."""
    schema_path = SCHEMA_DIR / name
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# task.schema.json
# ---------------------------------------------------------------------------

class TestTaskSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("task.schema.json")

    def test_valid_full_task(self, schema):
        doc = {
            "task_id": "task-001",
            "title": "Sample task",
            "scope": "implementation",
            "acceptance_criteria": ["Tests pass"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [
                {
                    "title": "Subtask 1",
                    "acceptance_criteria": ["AC1"],
                    "role": "builder",
                    "estimated_minutes": 60,
                }
            ],
        }
        jsonschema.validate(doc, schema)  # Should not raise

    def test_valid_minimal_task(self, schema):
        doc = {
            "task_id": "t1",
            "title": "T",
            "scope": "s",
            "acceptance_criteria": ["AC"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [{"title": "S", "acceptance_criteria": ["AC"]}],
        }
        jsonschema.validate(doc, schema)

    def test_invalid_missing_task_id(self, schema):
        doc = {
            "title": "T",
            "scope": "s",
            "acceptance_criteria": ["AC"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_empty_acceptance_criteria(self, schema):
        doc = {
            "task_id": "t1",
            "title": "T",
            "scope": "s",
            "acceptance_criteria": [],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_subtask_bad_role(self, schema):
        doc = {
            "task_id": "t1",
            "title": "T",
            "scope": "s",
            "acceptance_criteria": ["AC"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [
                {
                    "title": "S",
                    "acceptance_criteria": ["AC"],
                    "role": "invalid_role",
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# cli-envelope.schema.json
# ---------------------------------------------------------------------------

class TestCliEnvelopeSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("cli-envelope.schema.json")

    def test_valid_passed(self, schema):
        doc = {
            "status": "passed",
            "exit_code": 0,
            "stdout": "output here",
            "stderr": "",
        }
        jsonschema.validate(doc, schema)

    def test_valid_failed(self, schema):
        doc = {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": "error occurred",
        }
        jsonschema.validate(doc, schema)

    def test_valid_with_result(self, schema):
        doc = {
            "status": "passed",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "result": {"files_changed": ["a.py"]},
        }
        jsonschema.validate(doc, schema)

    def test_invalid_missing_status(self, schema):
        doc = {"exit_code": 0, "stdout": "", "stderr": ""}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_status(self, schema):
        doc = {"status": "unknown", "exit_code": 0, "stdout": "", "stderr": ""}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_extra_property(self, schema):
        doc = {
            "status": "passed",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "extra_field": "not allowed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# plan-result.schema.json
# ---------------------------------------------------------------------------

class TestPlanResultSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("plan-result.schema.json")

    def test_valid_done(self, schema):
        doc = {
            "status": "done",
            "implementation_contract": ["Build feature X"],
            "test_plan": ["pytest -v"],
            "open_questions": [],
        }
        jsonschema.validate(doc, schema)

    def test_valid_blocked_with_questions(self, schema):
        doc = {
            "status": "blocked",
            "implementation_contract": [],
            "test_plan": [],
            "open_questions": ["Need clarification on API design"],
        }
        jsonschema.validate(doc, schema)

    def test_valid_with_chunks(self, schema):
        doc = {
            "status": "done",
            "implementation_contract": ["Contract"],
            "test_plan": ["test"],
            "open_questions": [],
            "chunks": [
                {
                    "chunk_id": "T1-C01",
                    "title": "Chunk 1",
                    "estimated_minutes": 45,
                    "role": "builder",
                    "acceptance_criteria": [
                        {
                            "id": "AC-001",
                            "description": "Tests pass",
                            "verify_command": "pytest",
                        }
                    ],
                }
            ],
        }
        jsonschema.validate(doc, schema)

    def test_invalid_missing_status(self, schema):
        doc = {
            "implementation_contract": [],
            "test_plan": [],
            "open_questions": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_status(self, schema):
        doc = {
            "status": "running",
            "implementation_contract": [],
            "test_plan": [],
            "open_questions": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# implement-result.schema.json
# ---------------------------------------------------------------------------

class TestImplementResultSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("implement-result.schema.json")

    def test_valid_done(self, schema):
        doc = {
            "status": "done",
            "files_changed": ["a.py", "b.py"],
            "commands_executed": [
                {"status": "passed", "command": "echo ok", "return_code": 0}
            ],
            "failed_tests": [],
            "artifacts": ["output.log"],
        }
        jsonschema.validate(doc, schema)

    def test_valid_failed(self, schema):
        doc = {
            "status": "failed",
            "files_changed": [],
            "commands_executed": [],
            "failed_tests": [{"test": "test_a", "error": "assertion"}],
            "artifacts": [],
        }
        jsonschema.validate(doc, schema)

    def test_valid_blocked(self, schema):
        doc = {
            "status": "blocked",
            "files_changed": [],
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
        }
        jsonschema.validate(doc, schema)

    def test_invalid_missing_files_changed(self, schema):
        doc = {
            "status": "done",
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_status(self, schema):
        doc = {
            "status": "running",
            "files_changed": [],
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# review-result.schema.json
# ---------------------------------------------------------------------------

class TestReviewResultSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("review-result.schema.json")

    def test_valid_approved(self, schema):
        doc = {
            "claude_review": {"status": "approved", "notes": []},
            "codex_review": {"status": "implemented", "notes": []},
            "action_required": [],
            "go_no_go": False,
        }
        jsonschema.validate(doc, schema)

    def test_valid_blocked(self, schema):
        doc = {
            "claude_review": {"status": "changes_required", "notes": ["Fix X"]},
            "codex_review": {"status": "needs_revision", "notes": ["Redo Y"]},
            "action_required": ["Fix failing tests"],
            "go_no_go": True,
        }
        jsonschema.validate(doc, schema)

    def test_valid_with_optional_fields(self, schema):
        doc = {
            "work_id": "rev-001",
            "status": "ready_for_merge",
            "claude_review": {"status": "approved", "notes": []},
            "codex_review": {"status": "implemented", "notes": []},
            "action_required": [],
            "go_no_go": False,
            "open_questions": [],
            "references": {"plan": "plan.json"},
        }
        jsonschema.validate(doc, schema)

    def test_invalid_missing_go_no_go(self, schema):
        doc = {
            "claude_review": {"status": "approved"},
            "codex_review": {"status": "implemented"},
            "action_required": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_go_no_go_not_boolean(self, schema):
        doc = {
            "claude_review": {"status": "approved"},
            "codex_review": {"status": "implemented"},
            "action_required": [],
            "go_no_go": "yes",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


# ---------------------------------------------------------------------------
# retrospect.schema.json
# ---------------------------------------------------------------------------

class TestRetrospectSchema:
    @pytest.fixture
    def schema(self):
        return load_schema("retrospect.schema.json")

    def _make_valid_doc(self, **overrides):
        """Return a fully valid retrospect document, with optional overrides."""
        doc = {
            "work_id": "retro-001",
            "generated_at": "2026-02-15T12:00:00Z",
            "status": "ready",
            "summary": {
                "go_no_go": True,
                "issues_count": 1,
                "next_action_count": 2,
            },
            "next_plan": [
                {
                    "index": 1,
                    "type": "rework",
                    "title": "Fix failing integration test",
                    "owner": "codex",
                    "priority": "high",
                },
                {
                    "index": 2,
                    "type": "observe",
                    "title": "Monitor CI after merge",
                    "owner": "claude",
                    "priority": "medium",
                },
            ],
            "evidence": {
                "review_reference": "work/retro-001/review.json",
                "questions": ["Is the API contract stable?"],
            },
        }
        doc.update(overrides)
        return doc

    # -- valid cases ---------------------------------------------------------

    def test_valid_full_document(self, schema):
        doc = self._make_valid_doc()
        jsonschema.validate(doc, schema)  # Should not raise

    def test_valid_minimal_required_fields(self, schema):
        doc = {
            "status": "ready",
            "summary": {
                "go_no_go": False,
                "issues_count": 0,
                "next_action_count": 0,
            },
            "next_plan": [],
            "evidence": {
                "review_reference": "review.json",
                "questions": [],
            },
        }
        jsonschema.validate(doc, schema)

    def test_valid_blocked_status(self, schema):
        doc = self._make_valid_doc(status="blocked")
        jsonschema.validate(doc, schema)

    def test_valid_owner_both(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 1,
                    "type": "rework",
                    "title": "Pair refactoring session",
                    "owner": "both",
                    "priority": "low",
                }
            ]
        )
        jsonschema.validate(doc, schema)

    def test_valid_without_optional_work_id_and_generated_at(self, schema):
        doc = {
            "status": "ready",
            "summary": {
                "go_no_go": False,
                "issues_count": 0,
                "next_action_count": 0,
            },
            "next_plan": [],
            "evidence": {
                "review_reference": "r.json",
                "questions": [],
            },
        }
        jsonschema.validate(doc, schema)

    # -- invalid: missing required top-level fields -------------------------

    def test_invalid_missing_status(self, schema):
        doc = self._make_valid_doc()
        del doc["status"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_missing_summary(self, schema):
        doc = self._make_valid_doc()
        del doc["summary"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_missing_next_plan(self, schema):
        doc = self._make_valid_doc()
        del doc["next_plan"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_missing_evidence(self, schema):
        doc = self._make_valid_doc()
        del doc["evidence"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    # -- invalid: bad enum values -------------------------------------------

    def test_invalid_bad_status_enum(self, schema):
        doc = self._make_valid_doc(status="pending")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_action_type(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 1,
                    "type": "rewrite",
                    "title": "Bad type",
                    "owner": "claude",
                    "priority": "high",
                }
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_owner(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 1,
                    "type": "rework",
                    "title": "Bad owner",
                    "owner": "human",
                    "priority": "high",
                }
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_bad_priority(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 1,
                    "type": "observe",
                    "title": "Bad priority",
                    "owner": "codex",
                    "priority": "critical",
                }
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    # -- invalid: wrong types -----------------------------------------------

    def test_invalid_go_no_go_not_boolean(self, schema):
        doc = self._make_valid_doc()
        doc["summary"]["go_no_go"] = "yes"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_issues_count_negative(self, schema):
        doc = self._make_valid_doc()
        doc["summary"]["issues_count"] = -1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_next_action_count_not_integer(self, schema):
        doc = self._make_valid_doc()
        doc["summary"]["next_action_count"] = 1.5
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_action_index_zero(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 0,
                    "type": "rework",
                    "title": "Index too low",
                    "owner": "claude",
                    "priority": "high",
                }
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_questions_not_strings(self, schema):
        doc = self._make_valid_doc()
        doc["evidence"]["questions"] = [42, True]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    # -- invalid: missing required fields in nested objects -----------------

    def test_invalid_summary_missing_go_no_go(self, schema):
        doc = self._make_valid_doc()
        del doc["summary"]["go_no_go"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_action_missing_title(self, schema):
        doc = self._make_valid_doc(
            next_plan=[
                {
                    "index": 1,
                    "type": "rework",
                    "owner": "codex",
                    "priority": "high",
                }
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_invalid_evidence_missing_review_reference(self, schema):
        doc = self._make_valid_doc()
        del doc["evidence"]["review_reference"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)
