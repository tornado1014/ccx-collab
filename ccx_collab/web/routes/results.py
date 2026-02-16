"""Result file browser routes."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ccx_collab.config import get_results_dir

logger = logging.getLogger(__name__)
router = APIRouter(tags=["results"])


@router.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    """Result browser page."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "results/browser.html", {})


@router.get("/api/results")
async def list_results(work_id: str = ""):
    """List result files, optionally filtered by work_id."""
    results_dir = get_results_dir()
    if not results_dir.is_dir():
        return {"files": [], "directory": str(results_dir)}

    files = []
    for f in sorted(results_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if work_id and work_id not in f.name:
            continue
        stat = f.stat()
        files.append({
            "name": f.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })

    return {"files": files, "directory": str(results_dir)}


@router.get("/api/results/{filename}")
async def get_result_file(filename: str):
    """Read a specific result file."""
    # Path traversal protection
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    results_dir = get_results_dir()
    file_path = results_dir / safe_name
    if not file_path.is_file():
        raise HTTPException(404, f"File not found: {filename}")

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_raw": file_path.read_text(encoding="utf-8")}
