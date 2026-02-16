"""Configuration management routes."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ccx_collab.config import (
    CCX_COLLAB_DEFAULTS,
    _load_yaml_file,
    get_project_root,
    load_ccx_collab_config,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["config"])

RELEVANT_ENV_VARS = [
    "CLAUDE_CODE_CMD",
    "CODEX_CLI_CMD",
    "CLAUDE_CODEX_ROOT",
    "SIMULATE_AGENTS",
    "CCX_COLLAB_LOG_LEVEL",
]


class ConfigSaveRequest(BaseModel):
    content: str


@router.get("/settings/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration management page."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "settings/config.html", {})


@router.get("/api/config")
async def get_merged_config():
    """Return the merged configuration."""
    return load_ccx_collab_config()


@router.get("/api/config/layers")
async def get_config_layers():
    """Return configuration from each layer separately."""
    project_root = get_project_root()
    user_dir = Path.home() / ".ccx-collab"

    project_config_path = project_root / ".ccx-collab.yaml"
    user_config_path = user_dir / "config.yaml"

    return {
        "defaults": CCX_COLLAB_DEFAULTS,
        "user": {
            "path": str(user_config_path),
            "exists": user_config_path.is_file(),
            "content": _load_yaml_file(user_config_path),
        },
        "project": {
            "path": str(project_config_path),
            "exists": project_config_path.is_file(),
            "content": _load_yaml_file(project_config_path),
        },
        "merged": load_ccx_collab_config(),
    }


@router.get("/api/config/env")
async def get_env_vars():
    """Return relevant environment variables."""
    return {name: os.environ.get(name) for name in RELEVANT_ENV_VARS}


@router.put("/api/config/project")
async def save_project_config(body: ConfigSaveRequest):
    """Save project-level configuration."""
    try:
        data = yaml.safe_load(body.content)
        if not isinstance(data, dict):
            raise HTTPException(400, "YAML must be a mapping")
    except yaml.YAMLError as e:
        raise HTTPException(400, f"Invalid YAML: {e}")

    project_root = get_project_root()
    config_path = project_root / ".ccx-collab.yaml"
    config_path.write_text(body.content, encoding="utf-8")
    return {"status": "saved", "path": str(config_path)}
