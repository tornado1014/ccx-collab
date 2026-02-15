"""Configuration: project root, platform detection, pipeline config loading."""

from __future__ import annotations

import json
import os
import platform as _platform
from pathlib import Path
from typing import Any, Dict


def get_project_root() -> Path:
    """Find project root by looking for agent/ directory or CLAUDE_CODEX_ROOT env."""
    env_root = os.environ.get("CLAUDE_CODEX_ROOT", "").strip()
    if env_root:
        p = Path(env_root)
        if p.is_dir():
            return p

    # Walk up from this file's location
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "agent").is_dir():
            return current
        current = current.parent

    # Fallback: walk up from cwd
    current = Path.cwd()
    while current != current.parent:
        if (current / "agent").is_dir():
            return current
        current = current.parent

    return Path.cwd()


def get_platform() -> str:
    """Return platform identifier: 'macos', 'linux', or 'windows'."""
    system = _platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def get_results_dir(work_id: str = "") -> Path:
    """Return the results directory path."""
    root = get_project_root()
    return root / "agent" / "results"


def load_pipeline_config() -> Dict[str, Any]:
    """Load agent/pipeline-config.json, returning empty dict on failure."""
    config_path = get_project_root() / "agent" / "pipeline-config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}
