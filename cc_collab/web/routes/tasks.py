"""Task management routes."""
from __future__ import annotations

import json
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"])


def _get_tasks_dir() -> Path:
    """Return the tasks directory path."""
    from cc_collab.config import get_project_root
    return get_project_root() / "agent" / "tasks"


def _scan_tasks() -> list[dict]:
    """Scan agent/tasks/*.task.json and return list of task dicts with path info."""
    tasks_dir = _get_tasks_dir()
    tasks = []
    if not tasks_dir.is_dir():
        return tasks
    for f in sorted(tasks_dir.glob("*.task.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_path"] = str(f)
            data["_filename"] = f.name
            tasks.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read task file %s: %s", f, exc)
    return tasks


def _find_task_file(task_id: str) -> Path | None:
    """Find a task file by task_id."""
    tasks_dir = _get_tasks_dir()
    exact = tasks_dir / f"{task_id}.task.json"
    if exact.is_file():
        return exact
    for f in tasks_dir.glob("*.task.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("task_id") == task_id:
                return f
        except (json.JSONDecodeError, OSError):
            continue
    return None


@router.get("/tasks", response_class=HTMLResponse)
async def list_tasks(request: Request):
    """List all task files."""
    from cc_collab.web.app import templates
    tasks = _scan_tasks()
    return templates.TemplateResponse("tasks/list.html", {
        "request": request,
        "tasks": tasks,
    })


@router.get("/tasks/create", response_class=HTMLResponse)
async def create_task_form(request: Request):
    """Show task creation form."""
    from cc_collab.web.app import templates
    return templates.TemplateResponse("tasks/create.html", {"request": request})


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    """Show task detail page."""
    from cc_collab.web.app import templates
    task_file = _find_task_file(task_id)
    if task_file is None:
        return HTMLResponse("<p>Task not found</p>", status_code=404)
    data = json.loads(task_file.read_text(encoding="utf-8"))
    return templates.TemplateResponse("tasks/detail.html", {
        "request": request,
        "task": data,
        "task_json": json.dumps(data, indent=2, ensure_ascii=False),
    })


@router.post("/tasks")
async def create_task(
    task_id: str = Form(...),
    title: str = Form(...),
    template: str = Form("standard"),
):
    """Create a new task from form data."""
    from cc_collab.commands.tools import _build_task_template
    task_data = _build_task_template(task_id, title, template)

    tasks_dir = _get_tasks_dir()
    tasks_dir.mkdir(parents=True, exist_ok=True)
    out_path = tasks_dir / f"{task_id}.task.json"
    out_path.write_text(
        json.dumps(task_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.put("/tasks/{task_id}")
async def update_task(request: Request, task_id: str, task_json: str = Form(...)):
    """Update a task from JSON textarea."""
    task_file = _find_task_file(task_id)
    if task_file is None:
        return HTMLResponse("<p>Task not found</p>", status_code=404)
    try:
        data = json.loads(task_json)
    except json.JSONDecodeError as exc:
        return HTMLResponse(f"<p>Invalid JSON: {exc}</p>", status_code=400)
    task_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return HTMLResponse("<p>Task saved successfully.</p>")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task file."""
    task_file = _find_task_file(task_id)
    if task_file is None:
        return HTMLResponse("<p>Task not found</p>", status_code=404)
    task_file.unlink()
    return HTMLResponse("")


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    """Start a pipeline run for a task."""
    from cc_collab.web.db import get_db
    from cc_collab.web.models import PipelineRun, insert_pipeline_run, _now_iso

    task_file = _find_task_file(task_id)
    if task_file is None:
        return HTMLResponse("<p>Task not found</p>", status_code=404)

    work_id = hashlib.sha256(task_file.read_bytes()).hexdigest()[:12]
    run_id = str(uuid.uuid4())[:8]

    db = await get_db()
    run = PipelineRun(
        id=run_id,
        work_id=work_id,
        task_path=str(task_file),
        status="pending",
        started_at=_now_iso(),
    )
    await insert_pipeline_run(db, run)

    return HTMLResponse(
        f'<p>Pipeline started. Work ID: '
        f'<a href="/history/{run_id}">{work_id}</a></p>'
    )
