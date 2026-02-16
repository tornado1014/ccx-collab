"""Individual stage execution routes."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stages"])

STAGE_DEFINITIONS = {
    "validate": {
        "description": "Validate task file structure and schema",
        "fields": [
            {"name": "task_path", "label": "Task File", "type": "file", "required": True},
            {"name": "work_id", "label": "Work ID", "type": "text", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "plan": {
        "description": "Generate implementation plan via Claude",
        "fields": [
            {"name": "task_path", "label": "Task File", "type": "file", "required": True},
            {"name": "work_id", "label": "Work ID", "type": "text", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "split": {
        "description": "Split plan into dispatchable subtasks",
        "fields": [
            {"name": "task_path", "label": "Task File", "type": "file", "required": True},
            {"name": "plan", "label": "Plan File", "type": "file", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
            {"name": "matrix_output", "label": "Matrix Output", "type": "text", "required": False},
        ],
    },
    "implement": {
        "description": "Implement a subtask via Codex CLI",
        "fields": [
            {"name": "task_path", "label": "Task File", "type": "file", "required": True},
            {"name": "dispatch", "label": "Dispatch File", "type": "file", "required": False},
            {"name": "subtask_id", "label": "Subtask ID", "type": "text", "required": False},
            {"name": "work_id", "label": "Work ID", "type": "text", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "merge": {
        "description": "Merge implementation results",
        "fields": [
            {"name": "work_id", "label": "Work ID", "type": "text", "required": True},
            {"name": "kind", "label": "Kind", "type": "select", "options": ["implement"], "required": False},
            {"name": "results_dir", "label": "Results Directory", "type": "text", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "verify": {
        "description": "Run verification commands",
        "fields": [
            {"name": "work_id", "label": "Work ID", "type": "text", "required": True},
            {"name": "platform", "label": "Platform", "type": "select", "options": ["macos", "linux", "windows"], "required": False},
            {"name": "commands", "label": "Commands", "type": "text", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "review": {
        "description": "Review implementation results via Claude",
        "fields": [
            {"name": "work_id", "label": "Work ID", "type": "text", "required": True},
            {"name": "plan", "label": "Plan File", "type": "file", "required": False},
            {"name": "implement", "label": "Implement File", "type": "file", "required": False},
            {"name": "verify", "label": "Verify File", "type": "file", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
    "retrospect": {
        "description": "Generate retrospective from review",
        "fields": [
            {"name": "work_id", "label": "Work ID", "type": "text", "required": True},
            {"name": "review", "label": "Review File", "type": "file", "required": False},
            {"name": "out", "label": "Output Path", "type": "text", "required": False},
        ],
    },
}


class StageRunRequest(BaseModel):
    simulate: bool = False
    params: Dict[str, str] = {}


def _scan_available_files() -> Dict[str, List[str]]:
    """Scan agent/tasks and agent/results for available input files."""
    from ccx_collab.config import get_project_root
    root = get_project_root()
    result: Dict[str, List[str]] = {"tasks": [], "results": []}
    tasks_dir = root / "agent" / "tasks"
    results_dir = root / "agent" / "results"
    if tasks_dir.is_dir():
        result["tasks"] = sorted([str(f) for f in tasks_dir.glob("*.task.json")])
    if results_dir.is_dir():
        result["results"] = sorted([str(f) for f in results_dir.glob("*.json")])
    return result


@router.get("/stages", response_class=HTMLResponse)
async def stages_index(request: Request):
    """Stages index page showing all available stages."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "stages/index.html", {
        "stages": STAGE_DEFINITIONS,
    })


@router.get("/stages/{stage_name}", response_class=HTMLResponse)
async def stage_run_page(request: Request, stage_name: str):
    """Stage run form page."""
    if stage_name not in STAGE_DEFINITIONS:
        raise HTTPException(404, f"Unknown stage: {stage_name}")
    from ccx_collab.web.app import templates
    files = _scan_available_files()
    return templates.TemplateResponse(request, "stages/run.html", {
        "stage_name": stage_name,
        "stage_info": STAGE_DEFINITIONS[stage_name],
        "available_files": files,
    })


@router.get("/api/stages/{stage_name}/form")
async def stage_form_data(stage_name: str):
    """Return form fields and available files for a stage."""
    if stage_name not in STAGE_DEFINITIONS:
        raise HTTPException(404, f"Unknown stage: {stage_name}")
    files = _scan_available_files()
    return {
        "stage": stage_name,
        "fields": STAGE_DEFINITIONS[stage_name]["fields"],
        "description": STAGE_DEFINITIONS[stage_name]["description"],
        "available_files": files,
    }


@router.post("/api/stages/{stage_name}/run")
async def run_stage(stage_name: str, body: StageRunRequest):
    """Run a single pipeline stage."""
    if stage_name not in STAGE_DEFINITIONS:
        raise HTTPException(404, f"Unknown stage: {stage_name}")

    from ccx_collab.bridge import (
        run_validate, run_plan, run_split, run_implement,
        run_merge, run_verify, run_review, run_retrospect,
        setup_simulate_mode,
    )

    stage_funcs = {
        "validate": lambda p: run_validate(task=p.get("task_path", ""), work_id=p.get("work_id", ""), out=p.get("out", "")),
        "plan": lambda p: run_plan(task=p.get("task_path", ""), work_id=p.get("work_id", ""), out=p.get("out", "")),
        "split": lambda p: run_split(task=p.get("task_path", ""), plan=p.get("plan", ""), out=p.get("out", ""), matrix_output=p.get("matrix_output", "")),
        "implement": lambda p: run_implement(task=p.get("task_path", ""), dispatch=p.get("dispatch", ""), subtask_id=p.get("subtask_id", ""), work_id=p.get("work_id", ""), out=p.get("out", "")),
        "merge": lambda p: run_merge(work_id=p.get("work_id", ""), kind=p.get("kind", "implement"), results_dir=p.get("results_dir", ""), out=p.get("out", "")),
        "verify": lambda p: run_verify(work_id=p.get("work_id", ""), platform=p.get("platform", ""), commands=p.get("commands", ""), out=p.get("out", "")),
        "review": lambda p: run_review(work_id=p.get("work_id", ""), plan=p.get("plan", ""), implement=p.get("implement", ""), verify=p.get("verify", ""), out=p.get("out", "")),
        "retrospect": lambda p: run_retrospect(work_id=p.get("work_id", ""), review=p.get("review", ""), out=p.get("out", "")),
    }

    setup_simulate_mode(body.simulate)
    params = {k: v for k, v in body.params.items() if v}

    try:
        rc = await asyncio.to_thread(stage_funcs[stage_name], params)
    except Exception as exc:
        logger.exception("Stage %s failed with exception", stage_name)
        return {"stage": stage_name, "exit_code": 1, "status": "error", "error": str(exc)}

    return {
        "stage": stage_name,
        "exit_code": rc,
        "status": "completed" if rc == 0 else "failed",
    }
