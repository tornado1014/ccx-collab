"""Pipeline history and analytics routes."""
from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["history"])

RUNS_PER_PAGE = 20


@router.get("/history", response_class=HTMLResponse)
async def list_history(
    request: Request,
    status: str = Query("", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Pipeline run history list."""
    from cc_collab.web.app import templates
    from cc_collab.web.db import get_db
    from cc_collab.web.models import list_pipeline_runs

    db = await get_db()

    # Get total count for pagination
    count_q = "SELECT COUNT(*) FROM pipeline_runs"
    count_params: list = []
    if status:
        count_q += " WHERE status = ?"
        count_params.append(status)
    cursor = await db.execute(count_q, count_params)
    row = await cursor.fetchone()
    total = row[0] if row else 0
    total_pages = max(1, math.ceil(total / RUNS_PER_PAGE))
    page = min(page, total_pages)

    offset = (page - 1) * RUNS_PER_PAGE

    if status:
        # Filtered query with pagination
        cursor = await db.execute(
            "SELECT * FROM pipeline_runs WHERE status = ? "
            "ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (status, RUNS_PER_PAGE, offset),
        )
        rows = await cursor.fetchall()
        from cc_collab.web.models import PipelineRun
        runs = [PipelineRun(*r) for r in rows]
    else:
        runs = await list_pipeline_runs(db, limit=RUNS_PER_PAGE, offset=offset)

    return templates.TemplateResponse("history/list.html", {
        "request": request,
        "runs": runs,
        "filter_status": status,
        "page": page,
        "total_pages": total_pages,
    })


@router.get("/history/charts", response_class=HTMLResponse)
async def charts_page(request: Request):
    """Analytics charts page."""
    from cc_collab.web.app import templates
    return templates.TemplateResponse("history/charts.html", {"request": request})


@router.get("/history/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Detailed view of a pipeline run."""
    from cc_collab.web.app import templates
    from cc_collab.web.db import get_db
    from cc_collab.web.models import get_pipeline_run, list_stage_results

    db = await get_db()
    run = await get_pipeline_run(db, run_id)
    if run is None:
        return HTMLResponse("<p>Run not found</p>", status_code=404)

    stages = await list_stage_results(db, run_id)

    return templates.TemplateResponse("history/detail.html", {
        "request": request,
        "run": run,
        "stages": stages,
    })


@router.get("/api/history/stats")
async def history_stats():
    """Return pipeline statistics as JSON for charts."""
    from cc_collab.web.db import get_db

    db = await get_db()

    # Status counts
    cursor = await db.execute(
        "SELECT status, COUNT(*) as count FROM pipeline_runs GROUP BY status"
    )
    status_counts = {row[0]: row[1] for row in await cursor.fetchall()}

    # Average duration per stage (completed stages only)
    cursor = await db.execute(
        "SELECT stage_name, "
        "AVG(julianday(finished_at) - julianday(started_at)) * 86400 as avg_secs "
        "FROM stage_results "
        "WHERE status = 'completed' AND finished_at IS NOT NULL AND started_at IS NOT NULL "
        "GROUP BY stage_name "
        "ORDER BY avg_secs DESC"
    )
    avg_duration_by_stage = {
        row[0]: round(row[1], 1) if row[1] else 0
        for row in await cursor.fetchall()
    }

    # Daily run counts (last 30 days) as array of {date, count}
    cursor = await db.execute(
        "SELECT date(started_at) as day, COUNT(*) as count "
        "FROM pipeline_runs "
        "WHERE started_at IS NOT NULL "
        "GROUP BY date(started_at) "
        "ORDER BY day DESC LIMIT 30"
    )
    daily_runs = [
        {"date": row[0], "count": row[1]}
        for row in await cursor.fetchall()
    ]

    # Stage failure counts
    cursor = await db.execute(
        "SELECT stage_name, COUNT(*) as count "
        "FROM stage_results "
        "WHERE status = 'failed' "
        "GROUP BY stage_name "
        "ORDER BY count DESC"
    )
    stage_failure_counts = {row[0]: row[1] for row in await cursor.fetchall()}

    return JSONResponse({
        "status_counts": status_counts,
        "avg_duration_by_stage": avg_duration_by_stage,
        "daily_runs": daily_runs,
        "stage_failure_counts": stage_failure_counts,
        "total_runs": sum(status_counts.values()) if status_counts else 0,
    })
