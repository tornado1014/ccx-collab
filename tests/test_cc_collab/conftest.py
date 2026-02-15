"""Shared fixtures for cc-collab CLI tests."""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def example_task_path(project_root):
    """Return path to the example task file."""
    return project_root / "agent" / "tasks" / "example.task.json"


@pytest.fixture
def sample_task(tmp_path):
    """Create a minimal valid task JSON in a temp directory."""
    task = {
        "task_id": "test-task-001",
        "title": "Test Task",
        "scope": "Unit test scope",
        "risk_level": "low",
        "priority": "medium",
        "acceptance_criteria": [
            {
                "id": "AC-S00-1",
                "description": "Test passes",
                "verification": "echo ok",
                "type": "automated",
            }
        ],
        "subtasks": [
            {
                "subtask_id": "test-task-001-S01",
                "title": "First subtask",
                "role": "builder",
                "acceptance_criteria": [
                    {
                        "id": "AC-S01-1",
                        "description": "Sub test passes",
                        "verification": "echo ok",
                        "type": "automated",
                    }
                ],
            }
        ],
    }
    task_file = tmp_path / "test.task.json"
    task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")
    return task_file


@pytest.fixture(autouse=True)
def _clean_simulate_env():
    """Ensure SIMULATE_AGENTS is reset after each test."""
    old = os.environ.get("SIMULATE_AGENTS")
    yield
    if old is not None:
        os.environ["SIMULATE_AGENTS"] = old
    elif "SIMULATE_AGENTS" in os.environ:
        del os.environ["SIMULATE_AGENTS"]
