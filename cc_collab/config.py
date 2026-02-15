"""Configuration: project root, platform detection, pipeline config loading."""

from __future__ import annotations

import json
import logging
import os
import platform as _platform
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Built-in defaults for cc-collab configuration.
CC_COLLAB_DEFAULTS: Dict[str, Any] = {
    "results_dir": "agent/results",
    "retention_days": 30,
    "simulate": False,
    "verbose": False,
    "verify_commands": ["python3 -m pytest agent/tests/ -v"],
}


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


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict.

    Returns an empty dict if the file does not exist or contains invalid YAML.
    """
    if not path.is_file():
        logger.debug("YAML config file not found: %s", path)
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            logger.warning(
                "YAML config file %s did not produce a dict (got %s), ignoring",
                path,
                type(data).__name__,
            )
            return {}
        logger.debug("Loaded YAML config from %s (%d keys)", path, len(data))
        return data
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in config file %s: %s", path, exc)
        return {}
    except OSError as exc:
        logger.warning("Failed to read config file %s: %s", path, exc)
        return {}


def load_cc_collab_config(
    *,
    project_dir: Optional[Path] = None,
    user_dir: Optional[Path] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load and merge cc-collab configuration from all sources.

    Precedence (highest to lowest):
        1. cli_overrides  -- explicit CLI flags
        2. project config -- .cc-collab.yaml in the project root
        3. user config    -- ~/.cc-collab/config.yaml
        4. CC_COLLAB_DEFAULTS -- built-in defaults

    Parameters
    ----------
    project_dir:
        Directory to look for ``.cc-collab.yaml``.  Defaults to
        :func:`get_project_root`.
    user_dir:
        Directory to look for ``config.yaml``.  Defaults to
        ``~/.cc-collab``.
    cli_overrides:
        Key/value pairs provided via CLI flags.  ``None`` values are
        excluded (treated as "not provided").

    Returns
    -------
    Dict[str, Any]
        Merged configuration dictionary.
    """
    # Start with built-in defaults
    merged: Dict[str, Any] = dict(CC_COLLAB_DEFAULTS)

    # Layer 3: user-level config (~/.cc-collab/config.yaml)
    if user_dir is None:
        user_dir = Path.home() / ".cc-collab"
    user_config_path = user_dir / "config.yaml"
    user_cfg = _load_yaml_file(user_config_path)
    merged.update(user_cfg)

    # Layer 2: project-level config (.cc-collab.yaml in project root)
    if project_dir is None:
        project_dir = get_project_root()
    project_config_path = project_dir / ".cc-collab.yaml"
    project_cfg = _load_yaml_file(project_config_path)
    merged.update(project_cfg)

    # Layer 1: CLI overrides (highest precedence)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None:
                merged[key] = value

    logger.debug("Final merged cc-collab config: %s", merged)
    return merged
