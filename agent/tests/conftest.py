"""Shared test fixtures for the agent test suite."""
import json
import pathlib
import pytest


@pytest.fixture
def tmp_results_dir(tmp_path):
    """Provide a temporary results directory."""
    results = tmp_path / "results"
    results.mkdir()
    return results


@pytest.fixture
def sample_task():
    """Return a valid task dictionary for testing."""
    return {
        "task_id": "test-task-001",
        "title": "Sample Test Task",
        "scope": "testing",
        "risk_level": "low",
        "priority": "medium",
        "platform": ["both"],
        "acceptance_criteria": [
            "All tests pass",
            "No regressions introduced"
        ],
        "subtasks": [
            {
                "subtask_id": "test-task-001-S01",
                "title": "First subtask",
                "role": "builder",
                "platform": ["both"],
                "scope": "implementation",
                "estimated_minutes": 30,
                "acceptance_criteria": ["Subtask completes successfully"]
            }
        ]
    }


@pytest.fixture
def sample_task_file(tmp_path, sample_task):
    """Write sample task to a temporary file and return the path."""
    task_file = tmp_path / "test-task.json"
    task_file.write_text(json.dumps(sample_task, indent=2))
    return task_file


@pytest.fixture
def sample_envelope():
    """Return a valid CLI envelope dictionary."""
    return {
        "status": "passed",
        "exit_code": 0,
        "stdout": json.dumps({"result": {"files_changed": ["test.py"]}}),
        "stderr": "",
        "result": {"files_changed": ["test.py"]}
    }
