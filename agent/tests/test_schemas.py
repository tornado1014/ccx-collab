"""Schema validation tests for all JSON schemas in agent/schemas/."""

import json
import pathlib
import re

import jsonschema
import pytest

SCHEMA_DIR = pathlib.Path(__file__).resolve().parents[1] / "schemas"

ALL_SCHEMA_FILES = sorted(SCHEMA_DIR.glob("*.schema.json"))


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


# ---------------------------------------------------------------------------
# Schema version management tests
# ---------------------------------------------------------------------------

class TestSchemaVersionManagement:
    """Verify that all schemas have proper version metadata ($id, $schema, version property)."""

    @pytest.fixture(params=[p.name for p in ALL_SCHEMA_FILES], ids=[p.stem for p in ALL_SCHEMA_FILES])
    def schema_entry(self, request):
        """Parametrized fixture yielding (filename, schema_dict) for each schema."""
        name = request.param
        return name, load_schema(name)

    def test_all_schemas_have_dollar_id(self, schema_entry):
        name, schema = schema_entry
        assert "$id" in schema, f"{name} is missing the $id field"

    def test_dollar_id_contains_version_string(self, schema_entry):
        name, schema = schema_entry
        dollar_id = schema.get("$id", "")
        # Version must be a semver-like string (vX.Y.Z) in the URI
        assert re.search(r"/v\d+\.\d+\.\d+$", dollar_id), (
            f"{name}: $id '{dollar_id}' does not end with a version like /vX.Y.Z"
        )

    def test_dollar_id_uri_format(self, schema_entry):
        name, schema = schema_entry
        dollar_id = schema.get("$id", "")
        assert dollar_id.startswith("https://cc-collab.dev/schemas/"), (
            f"{name}: $id should start with https://cc-collab.dev/schemas/"
        )

    def test_all_schemas_have_dollar_schema(self, schema_entry):
        name, schema = schema_entry
        assert "$schema" in schema, f"{name} is missing the $schema field"
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", (
            f"{name}: $schema should reference draft/2020-12"
        )

    def test_version_property_defined(self, schema_entry):
        name, schema = schema_entry
        props = schema.get("properties", {})
        assert "version" in props, f"{name} does not define a 'version' property"
        version_prop = props["version"]
        assert version_prop.get("type") == "string", (
            f"{name}: version property should have type 'string'"
        )
        assert "const" in version_prop, (
            f"{name}: version property should have a 'const' constraint"
        )

    def test_version_const_matches_id(self, schema_entry):
        """The const version in properties must match the version in $id."""
        name, schema = schema_entry
        dollar_id = schema.get("$id", "")
        id_match = re.search(r"/v(\d+\.\d+\.\d+)$", dollar_id)
        assert id_match, f"{name}: cannot extract version from $id"
        id_version = id_match.group(1)
        const_version = schema.get("properties", {}).get("version", {}).get("const")
        assert const_version == id_version, (
            f"{name}: version const '{const_version}' does not match $id version '{id_version}'"
        )

    def test_version_is_optional_for_backward_compat(self, schema_entry):
        """Version must NOT be in the required list (backward compatibility)."""
        name, schema = schema_entry
        required = schema.get("required", [])
        assert "version" not in required, (
            f"{name}: 'version' should not be required (backward compatibility)"
        )

    def test_version_property_has_default(self, schema_entry):
        name, schema = schema_entry
        version_prop = schema.get("properties", {}).get("version", {})
        assert "default" in version_prop, (
            f"{name}: version property should have a default value"
        )
        assert version_prop["default"] == version_prop.get("const"), (
            f"{name}: version default should match the const value"
        )


class TestSchemaVersionBackwardCompatibility:
    """Verify that documents without a version field still validate against updated schemas."""

    def test_task_without_version_still_valid(self):
        schema = load_schema("task.schema.json")
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

    def test_task_with_version_valid(self):
        schema = load_schema("task.schema.json")
        doc = {
            "version": "1.0.0",
            "task_id": "t1",
            "title": "T",
            "scope": "s",
            "acceptance_criteria": ["AC"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [{"title": "S", "acceptance_criteria": ["AC"]}],
        }
        jsonschema.validate(doc, schema)

    def test_task_with_wrong_version_fails(self):
        schema = load_schema("task.schema.json")
        doc = {
            "version": "2.0.0",
            "task_id": "t1",
            "title": "T",
            "scope": "s",
            "acceptance_criteria": ["AC"],
            "risk_level": "low",
            "priority": "high",
            "subtasks": [{"title": "S", "acceptance_criteria": ["AC"]}],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)

    def test_cli_envelope_without_version_still_valid(self):
        schema = load_schema("cli-envelope.schema.json")
        doc = {
            "status": "passed",
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
        }
        jsonschema.validate(doc, schema)

    def test_cli_envelope_with_version_valid(self):
        schema = load_schema("cli-envelope.schema.json")
        doc = {
            "version": "1.0.0",
            "status": "passed",
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
        }
        jsonschema.validate(doc, schema)

    def test_plan_result_without_version_still_valid(self):
        schema = load_schema("plan-result.schema.json")
        doc = {
            "status": "done",
            "implementation_contract": ["Build X"],
            "test_plan": ["pytest"],
            "open_questions": [],
        }
        jsonschema.validate(doc, schema)

    def test_implement_result_without_version_still_valid(self):
        schema = load_schema("implement-result.schema.json")
        doc = {
            "status": "done",
            "files_changed": ["a.py"],
            "commands_executed": [],
            "failed_tests": [],
            "artifacts": [],
        }
        jsonschema.validate(doc, schema)

    def test_review_result_without_version_still_valid(self):
        schema = load_schema("review-result.schema.json")
        doc = {
            "claude_review": {"status": "approved", "notes": []},
            "codex_review": {"status": "implemented", "notes": []},
            "action_required": [],
            "go_no_go": True,
        }
        jsonschema.validate(doc, schema)

    def test_retrospect_without_version_still_valid(self):
        schema = load_schema("retrospect.schema.json")
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
