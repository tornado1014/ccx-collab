"""Pipeline execution and monitoring API routes."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from ccx_collab.web.sse import sse_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

PIPELINE_STAGES = [
    "validate",
    "plan",
    "split",
    "implement",
    "merge",
    "verify",
    "review",
]


# --- Request / Response models ---


class PipelineRunRequest(BaseModel):
    task_path: str
    work_id: str = ""
    simulate: bool = False
    resume: bool = False
    force_stage: str | None = None
    stop_after_stage: str | None = None


class PipelineStatusResponse(BaseModel):
    id: str
    work_id: str
    status: str
    current_stage: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    task_path: str | None = None


# --- Background pipeline runner ---


async def _resolve_stages_to_run(
    db, work_id: str, resume: bool, force_stage: str | None,
) -> list[str]:
    """Determine which stages to run based on resume/force-stage options."""
    if force_stage:
        if force_stage not in PIPELINE_STAGES:
            raise ValueError(f"Unknown stage: {force_stage}")
        idx = PIPELINE_STAGES.index(force_stage)
        return PIPELINE_STAGES[idx:]

    if resume:
        from ccx_collab.web.models import list_stage_results

        # Find the latest run for this work_id
        cursor = await db.execute(
            "SELECT id FROM pipeline_runs WHERE work_id = ? ORDER BY started_at DESC LIMIT 1",
            (work_id,),
        )
        row = await cursor.fetchone()
        if row:
            last_run_id = row[0]
            results = await list_stage_results(db, last_run_id)
            completed_stages = {r.stage_name for r in results if r.status == "completed"}
            # Find first incomplete stage
            for i, stage in enumerate(PIPELINE_STAGES):
                if stage not in completed_stages:
                    return PIPELINE_STAGES[i:]

    return list(PIPELINE_STAGES)


async def _run_pipeline_background(
    run_id: str,
    work_id: str,
    task_path: str,
    simulate: bool,
    resume: bool = False,
    force_stage: str | None = None,
    stop_after_stage: str | None = None,
) -> None:
    """Execute the full pipeline in a background thread, publishing SSE events."""
    from ccx_collab.bridge import (
        run_implement,
        run_merge,
        run_plan,
        run_review,
        run_split,
        run_validate,
        run_verify,
        setup_simulate_mode,
    )
    from ccx_collab.config import get_platform
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import (
        StageResult,
        insert_stage_result,
        update_pipeline_run_status,
    )
    from ccx_collab.web.webhook import trigger_webhooks

    db = await get_db()

    if simulate:
        setup_simulate_mode(True)

    results_dir = "agent/results"
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    platform = get_platform()

    # Path templates
    validation_path = f"{results_dir}/validation_{work_id}.json"
    plan_path = f"{results_dir}/plan_{work_id}.json"
    dispatch_path = f"{results_dir}/dispatch_{work_id}.json"
    dispatch_matrix_path = f"{results_dir}/dispatch_{work_id}.matrix.json"
    implement_path = f"{results_dir}/implement_{work_id}.json"
    verify_path = f"{results_dir}/verify_{work_id}_{platform}.json"
    review_path = f"{results_dir}/review_{work_id}.json"

    stage_funcs = {
        "validate": lambda: run_validate(
            task=task_path, work_id=work_id, out=validation_path
        ),
        "plan": lambda: run_plan(task=task_path, work_id=work_id, out=plan_path),
        "split": lambda: run_split(
            task=task_path,
            plan=plan_path,
            out=dispatch_path,
            matrix_output=dispatch_matrix_path,
        ),
        "implement": lambda: _run_implement_stage(
            task_path, dispatch_path, work_id, results_dir
        ),
        "merge": lambda: run_merge(
            work_id=work_id,
            kind="implement",
            results_dir=results_dir,
            dispatch=dispatch_path,
            out=implement_path,
        ),
        "verify": lambda: run_verify(
            work_id=work_id, platform=platform, out=verify_path
        ),
        "review": lambda: run_review(
            work_id=work_id,
            plan=plan_path,
            implement=implement_path,
            verify=verify_path,
            out=review_path,
        ),
    }

    try:
        # Resolve which stages to run
        stages_to_run = await _resolve_stages_to_run(db, work_id, resume, force_stage)

        # Webhook: pipeline started
        await trigger_webhooks("pipeline_started", {
            "work_id": work_id, "task_path": task_path,
            "stages": stages_to_run,
        })

        for stage in stages_to_run:
            now = datetime.now(timezone.utc).isoformat()

            # Update run status
            await update_pipeline_run_status(
                db, run_id, "running", current_stage=stage
            )
            await sse_manager.publish_stage_update(work_id, stage, "running")

            # Run bridge function in a thread (they are synchronous)
            rc = await asyncio.to_thread(stage_funcs[stage])

            finished = datetime.now(timezone.utc).isoformat()
            stage_status = "completed" if rc == 0 else "failed"

            # Record stage result
            await insert_stage_result(
                db,
                StageResult(
                    id=None,
                    run_id=run_id,
                    stage_name=stage,
                    status=stage_status,
                    started_at=now,
                    finished_at=finished,
                ),
            )

            if rc != 0:
                await update_pipeline_run_status(
                    db, run_id, "failed",
                    current_stage=stage,
                    finished_at=finished,
                )
                await sse_manager.publish_stage_update(
                    work_id, stage, "failed", detail=f"exit code {rc}"
                )
                await sse_manager.publish_pipeline_complete(work_id, "failed")
                # Webhook: stage failed + pipeline failed
                await trigger_webhooks("stage_failed", {
                    "work_id": work_id, "stage": stage, "exit_code": rc,
                })
                await trigger_webhooks("pipeline_failed", {"work_id": work_id})
                return

            await sse_manager.publish_stage_update(work_id, stage, "completed")
            # Webhook: stage completed
            await trigger_webhooks("stage_completed", {
                "work_id": work_id, "stage": stage,
            })

            # Stop after specified stage for review gate
            if stop_after_stage and stage == stop_after_stage:
                await update_pipeline_run_status(
                    db, run_id, "awaiting_review",
                    current_stage=stage,
                )
                await sse_manager.publish_stage_update(
                    work_id, stage, "awaiting_review",
                    detail="Waiting for user review",
                )
                return

        # All stages passed
        await update_pipeline_run_status(
            db, run_id, "completed",
            current_stage=stages_to_run[-1] if stages_to_run else "review",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        await sse_manager.publish_pipeline_complete(work_id, "completed")
        # Webhook: pipeline completed
        await trigger_webhooks("pipeline_completed", {"work_id": work_id})

    except Exception:
        logger.exception("Pipeline %s crashed", work_id)
        await update_pipeline_run_status(
            db, run_id, "failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        await sse_manager.publish_pipeline_complete(work_id, "failed")
        await trigger_webhooks("pipeline_failed", {"work_id": work_id})


def _run_implement_stage(
    task_path: str, dispatch_path: str, work_id: str, results_dir: str
) -> int:
    """Run parallel subtask implementation (synchronous)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from ccx_collab.bridge import run_implement

    dispatch_data = json.loads(Path(dispatch_path).read_text(encoding="utf-8"))
    subtasks = dispatch_data.get("subtasks", [])
    if not subtasks:
        return 0

    failures = 0
    max_workers = min(4, len(subtasks))

    def _run_subtask(st):
        subtask_id = st["subtask_id"]
        out = f"{results_dir}/implement_{work_id}_{subtask_id}.json"
        return run_implement(
            task=task_path,
            dispatch=dispatch_path,
            subtask_id=subtask_id,
            work_id=work_id,
            out=out,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_subtask, st): st for st in subtasks}
        for future in as_completed(futures):
            if future.result() != 0:
                failures += 1

    return 1 if failures > 0 else 0


# --- Endpoints ---


@router.post("/run")
async def start_pipeline(body: PipelineRunRequest):
    """Start a pipeline run in the background."""
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import PipelineRun, insert_pipeline_run

    task_path = body.task_path
    if not Path(task_path).is_file():
        raise HTTPException(status_code=400, detail=f"Task file not found: {task_path}")

    work_id = body.work_id
    if not work_id:
        work_id = hashlib.sha256(Path(task_path).read_bytes()).hexdigest()[:12]

    # Validate force_stage
    if body.force_stage and body.force_stage not in PIPELINE_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown stage: {body.force_stage}. Valid stages: {PIPELINE_STAGES}",
        )

    db = await get_db()
    run_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    await insert_pipeline_run(
        db,
        PipelineRun(
            id=run_id,
            work_id=work_id,
            task_path=task_path,
            status="running",
            started_at=now,
            current_stage="validate",
        ),
    )

    # Launch background task
    asyncio.create_task(
        _run_pipeline_background(
            run_id=run_id,
            work_id=work_id,
            task_path=task_path,
            simulate=body.simulate,
            resume=body.resume,
            force_stage=body.force_stage,
            stop_after_stage=body.stop_after_stage,
        )
    )

    return {"work_id": work_id, "run_id": run_id, "status": "started"}


@router.get("/{work_id}/status", response_model=PipelineStatusResponse)
async def pipeline_status(work_id: str):
    """Get current pipeline status from DB."""
    from ccx_collab.web.db import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, work_id, status, current_stage, started_at, finished_at, task_path "
        "FROM pipeline_runs WHERE work_id = ? ORDER BY started_at DESC LIMIT 1",
        (work_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run not found: {work_id}")

    return PipelineStatusResponse(
        id=row["id"],
        work_id=row["work_id"],
        status=row["status"],
        current_stage=row["current_stage"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        task_path=row["task_path"],
    )


@router.get("/{work_id}/stream")
async def pipeline_stream(work_id: str):
    """SSE stream for real-time pipeline events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = sse_manager.subscribe(work_id)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event = message["event"]
                    data = message["data"]
                    yield f"event: {event}\ndata: {data}\n\n"
                    if event == "pipeline_complete":
                        break
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            sse_manager.unsubscribe(work_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{work_id}/cancel")
async def cancel_pipeline(work_id: str):
    """Cancel a running pipeline (marks as cancelled in DB)."""
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import update_pipeline_run_status

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, status FROM pipeline_runs WHERE work_id = ? ORDER BY started_at DESC LIMIT 1",
        (work_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run not found: {work_id}")
    if row["status"] != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline is not running (status={row['status']})",
        )

    await update_pipeline_run_status(
        db, row["id"], "cancelled",
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    await sse_manager.publish_pipeline_complete(work_id, "cancelled")

    return {"work_id": work_id, "status": "cancelled"}
