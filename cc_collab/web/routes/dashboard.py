"""Dashboard main page route."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page — shows recent runs and status summary."""
    from cc_collab.web.app import templates
    from cc_collab.web.db import get_db

    db = await get_db()

    # Recent pipeline runs (last 10)
    cursor = await db.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10"
    )
    recent_runs = await cursor.fetchall()

    # Status summary counts
    cursor = await db.execute(
        "SELECT status, COUNT(*) as count FROM pipeline_runs GROUP BY status"
    )
    status_counts = {row["status"]: row["count"] for row in await cursor.fetchall()}

    # Currently running pipelines
    cursor = await db.execute(
        "SELECT * FROM pipeline_runs WHERE status = 'running' ORDER BY started_at DESC"
    )
    running = await cursor.fetchall()

    if templates is None:
        # Fallback JSON response when templates are not available
        return HTMLResponse(
            content="<h1>cc-collab Dashboard</h1>"
            f"<p>Total runs: {sum(status_counts.values()) if status_counts else 0}</p>"
            f"<p>Running: {len(running)}</p>",
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_runs": recent_runs,
            "status_counts": status_counts,
            "running_pipelines": running,
            "total_runs": sum(status_counts.values()) if status_counts else 0,
        },
    )
