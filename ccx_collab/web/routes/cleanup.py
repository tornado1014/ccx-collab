"""Cleanup routes for old pipeline results."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ccx_collab.config import get_project_root, get_results_dir

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cleanup"])


class CleanupRequest(BaseModel):
    results_dir: str = ""
    retention_days: int = 30


def _validate_path(results_dir: str) -> Path:
    """Validate results directory path against traversal attacks."""
    if not results_dir:
        return get_results_dir()
    results_path = Path(results_dir).resolve()
    allowed_base = get_project_root().resolve()
    if not str(results_path).startswith(str(allowed_base)):
        raise HTTPException(400, "Invalid results directory")
    return results_path


def _perform_cleanup(results_dir: Path, retention_days: int, dry_run: bool = True) -> Dict[str, Any]:
    """Core cleanup logic shared by CLI and web."""
    if not results_dir.is_dir():
        return {"files": [], "deleted_count": 0, "total_size": 0, "error": "Directory not found"}

    cutoff = time.time() - (retention_days * 86400)
    files_to_delete: List[Dict[str, Any]] = []
    total_size = 0

    for f in sorted(results_dir.glob("*.json")):
        if not f.is_file():
            continue
        if f.stat().st_mtime >= cutoff:
            continue
        file_size = f.stat().st_size
        files_to_delete.append({
            "name": f.name,
            "path": str(f),
            "size": file_size,
            "mtime": f.stat().st_mtime,
        })
        total_size += file_size

        if not dry_run:
            f.unlink()

    return {
        "files": files_to_delete,
        "deleted_count": len(files_to_delete),
        "total_size": total_size,
        "dry_run": dry_run,
    }


@router.get("/settings/cleanup", response_class=HTMLResponse)
async def cleanup_page(request: Request):
    """Cleanup settings page."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "settings/cleanup.html", {})


@router.post("/api/cleanup/preview")
async def cleanup_preview(body: CleanupRequest):
    """Preview files that would be deleted."""
    results_path = _validate_path(body.results_dir)
    return _perform_cleanup(results_path, body.retention_days, dry_run=True)


@router.post("/api/cleanup/execute")
async def cleanup_execute(body: CleanupRequest):
    """Execute cleanup (actually delete files)."""
    results_path = _validate_path(body.results_dir)
    return _perform_cleanup(results_path, body.retention_days, dry_run=False)
