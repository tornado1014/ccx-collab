"""Configuration: project root, platform detection, pipeline config loading."""

from __future__ import annotations

import json
import logging
import os
import platform as _platform
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Find project root by looking for agent/ directory or CLAUDE_CODEX_ROOT env."""
    env_root = os.environ.get("CLAUDE_CODEX_ROOT", "").strip()
    if env_root:
        p = Path(env_root)
        if p.is_dir():
            logger.debug("Project root from CLAUDE_CODEX_ROOT env: %s", p)
            return p
        logger.debug("CLAUDE_CODEX_ROOT set but not a valid directory: %s", env_root)

    # Walk up from this file's location
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "agent").is_dir():
            logger.debug("Project root detected from file location: %s", current)
            return current
        current = current.parent

    # Fallback: walk up from cwd
    current = Path.cwd()
    while current != current.parent:
        if (current / "agent").is_dir():
            logger.debug("Project root detected from cwd traversal: %s", current)
            return current
        current = current.parent

    logger.debug("Project root fallback to cwd: %s", Path.cwd())
    return Path.cwd()


def get_platform() -> str:
    """Return platform identifier: 'macos', 'linux', or 'windows'."""
    system = _platform.system().lower()
    if system == "darwin":
        result = "macos"
    elif system == "windows":
        result = "windows"
    else:
        result = "linux"
    logger.debug("Platform detected: %s (system=%s)", result, system)
    return result


def get_results_dir(work_id: str = "") -> Path:
    """Return the results directory path."""
    root = get_project_root()
    results_dir = root / "agent" / "results"
    logger.debug("Results directory: %s", results_dir)
    return results_dir


def load_pipeline_config() -> Dict[str, Any]:
    """Load agent/pipeline-config.json, returning empty dict on failure."""
    config_path = get_project_root() / "agent" / "pipeline-config.json"
    if config_path.exists():
        logger.debug("Loading pipeline config from %s", config_path)
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            logger.debug("Pipeline config loaded successfully (%d top-level keys)", len(config))
            return config
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Failed to load pipeline config: %s", exc)
            return {}
    logger.debug("Pipeline config not found at %s", config_path)
    return {}
