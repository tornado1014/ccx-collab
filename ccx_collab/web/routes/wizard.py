"""Guided wizard workflow routes."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wizard"])

STAGE_LABELS = {
    "validate": ("Check Requirements", "Checking requirements..."),
    "plan": ("Create Plan", "Creating plan..."),
    "split": ("Divide Tasks", "Dividing tasks..."),
    "implement": ("Build Code", "Building code..."),
    "merge": ("Combine Results", "Combining results..."),
    "verify": ("Run Tests", "Running tests..."),
    "review": ("Quality Check", "Checking quality..."),
}


def _get_tasks_dir() -> Path:
    from ccx_collab.config import get_project_root

    return get_project_root() / "agent" / "tasks"


def _sanitize_id(text: str) -> str:
    """Generate a safe task_id from goal text."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", text).split()[:4]
    slug = "-".join(w.lower() for w in words) or "task"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


# --- Request models ---


class WizardStartRequest(BaseModel):
    goal: str
    complexity: str = "standard"
    simulate: bool = False


class WizardApproveRequest(BaseModel):
    simulate: bool = False


# --- Endpoints ---


@router.get("/wizard", response_class=HTMLResponse)
async def wizard_page(request: Request):
    from ccx_collab.web.app import templates

    return templates.TemplateResponse(request, "wizard/start.html")


@router.post("/api/wizard/start")
async def wizard_start(body: WizardStartRequest):
    """Create task from goal description and start Phase 1 (validate + plan)."""
    from ccx_collab.commands.tools import _build_task_template
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import PipelineRun, insert_pipeline_run
    from ccx_collab.web.routes.pipeline import _run_pipeline_background

    # 1. Generate task file from goal
    task_id = _sanitize_id(body.goal)
    task_data = _build_task_template(task_id, body.goal, body.complexity)
    task_data["scope"] = body.goal
    task_data["acceptance_criteria"][0]["description"] = body.goal

    tasks_dir = _get_tasks_dir()
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_path = tasks_dir / f"{task_id}.task.json"
    task_path.write_text(
        json.dumps(task_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 2. Start pipeline with stop_after_stage="plan"
    work_id = hashlib.sha256(task_path.read_bytes()).hexdigest()[:12]
    run_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    await insert_pipeline_run(
        db,
        PipelineRun(
            id=run_id,
            work_id=work_id,
            task_path=str(task_path),
            status="running",
            started_at=now,
            current_stage="validate",
        ),
    )

    asyncio.create_task(
        _run_pipeline_background(
            run_id=run_id,
            work_id=work_id,
            task_path=str(task_path),
            simulate=body.simulate,
            stop_after_stage="plan",
        )
    )

    return {
        "run_id": run_id,
        "work_id": work_id,
        "task_id": task_id,
        "redirect": f"/wizard/{run_id}/review",
    }


@router.get("/wizard/{run_id}/review", response_class=HTMLResponse)
async def wizard_review(request: Request, run_id: str):
    """Show plan review page."""
    from ccx_collab.web.app import templates
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import get_pipeline_run

    db = await get_db()
    run = await get_pipeline_run(db, run_id)
    if run is None:
        return HTMLResponse("<p>Run not found</p>", status_code=404)

    # Read plan result file if exists
    plan_data = None
    task_data = None
    results_dir = Path("agent/results")
    plan_file = results_dir / f"plan_{run.work_id}.json"
    if plan_file.is_file():
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    task_file = Path(run.task_path)
    if task_file.is_file():
        task_data = json.loads(task_file.read_text(encoding="utf-8"))

    return templates.TemplateResponse(
        request,
        "wizard/review.html",
        {
            "run": run,
            "plan": plan_data,
            "task": task_data,
        },
    )


@router.post("/api/wizard/{run_id}/approve")
async def wizard_approve(run_id: str, body: WizardApproveRequest):
    """Approve plan and resume pipeline from split stage."""
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import get_pipeline_run, update_pipeline_run_status
    from ccx_collab.web.routes.pipeline import _run_pipeline_background

    db = await get_db()
    run = await get_pipeline_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_review":
        raise HTTPException(
            status_code=409,
            detail=f"Run is not awaiting review (status={run.status})",
        )

    await update_pipeline_run_status(db, run_id, "running", current_stage="split")

    asyncio.create_task(
        _run_pipeline_background(
            run_id=run_id,
            work_id=run.work_id,
            task_path=run.task_path,
            simulate=body.simulate,
            force_stage="split",
        )
    )

    return {
        "status": "resumed",
        "redirect": f"/wizard/{run_id}/progress",
    }


@router.get("/wizard/{run_id}/progress", response_class=HTMLResponse)
async def wizard_progress(request: Request, run_id: str):
    """Show execution progress page."""
    from ccx_collab.web.app import templates
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import get_pipeline_run, list_stage_results

    db = await get_db()
    run = await get_pipeline_run(db, run_id)
    if run is None:
        return HTMLResponse("<p>Run not found</p>", status_code=404)

    stages = await list_stage_results(db, run_id)
    stage_map = {s.stage_name: s.status for s in stages}

    return templates.TemplateResponse(
        request,
        "wizard/progress.html",
        {
            "run": run,
            "stage_map": stage_map,
            "stage_labels": STAGE_LABELS,
        },
    )


@router.get("/wizard/{run_id}/done", response_class=HTMLResponse)
async def wizard_done(request: Request, run_id: str):
    """Show results page."""
    from ccx_collab.web.app import templates
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import get_pipeline_run

    db = await get_db()
    run = await get_pipeline_run(db, run_id)
    if run is None:
        return HTMLResponse("<p>Run not found</p>", status_code=404)

    review_data = None
    review_file = Path(f"agent/results/review_{run.work_id}.json")
    if review_file.is_file():
        review_data = json.loads(review_file.read_text(encoding="utf-8"))

    return templates.TemplateResponse(
        request,
        "wizard/done.html",
        {
            "run": run,
            "review": review_data,
        },
    )
