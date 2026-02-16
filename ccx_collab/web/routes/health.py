"""Health check routes."""
from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ccx_collab.config import get_results_dir

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


async def _check_cli(name: str) -> dict:
    """Check if a CLI tool is available."""
    try:
        result = await asyncio.to_thread(
            subprocess.run, [name, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return {"available": result.returncode == 0, "version": result.stdout.strip() or result.stderr.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "version": None}


def _disk_usage(path: Path) -> dict:
    """Get disk usage info for a path."""
    import shutil
    try:
        usage = shutil.disk_usage(str(path.parent if path.is_file() else path))
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": round(usage.used / usage.total * 100, 1) if usage.total else 0,
        }
    except OSError:
        return {"total": 0, "used": 0, "free": 0, "percent": 0}


@router.get("/settings/health", response_class=HTMLResponse)
async def health_page(request: Request):
    """Health check page."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "settings/health.html", {})


@router.get("/api/health")
async def health_api():
    """System health check API."""
    from ccx_collab.web.db import DB_PATH

    results_dir = get_results_dir()
    claude_info = await _check_cli("claude")
    codex_info = await _check_cli("codex")

    return {
        "claude_code": claude_info,
        "codex_cli": codex_info,
        "python_version": platform.python_version(),
        "ccx_collab_version": "0.4.0",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "disk_usage": _disk_usage(results_dir),
        "db_size": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "db_path": str(DB_PATH),
        "results_dir": str(results_dir),
        "results_count": len(list(results_dir.glob("*.json"))) if results_dir.is_dir() else 0,
    }
