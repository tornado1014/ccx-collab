"""Dataclass-based model definitions and SQL helpers for the web dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# CREATE TABLE statements
# ---------------------------------------------------------------------------

CREATE_PIPELINE_RUNS = """\
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          TEXT PRIMARY KEY,
    work_id     TEXT NOT NULL,
    task_path   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    started_at  TEXT,
    finished_at TEXT,
    current_stage TEXT,
    config_json TEXT
);
"""

CREATE_STAGE_RESULTS = """\
CREATE TABLE IF NOT EXISTS stage_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(id),
    stage_name  TEXT NOT NULL,
    status      TEXT NOT NULL,
    result_json TEXT,
    started_at  TEXT,
    finished_at TEXT
);
"""

CREATE_WEBHOOK_CONFIGS = """\
CREATE TABLE IF NOT EXISTS webhook_configs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    url        TEXT NOT NULL,
    events     TEXT NOT NULL DEFAULT '[]',
    active     BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""

CREATE_WEBHOOK_LOGS = """\
CREATE TABLE IF NOT EXISTS webhook_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id   INTEGER NOT NULL REFERENCES webhook_configs(id),
    event       TEXT NOT NULL,
    status_code INTEGER,
    response    TEXT,
    sent_at     TEXT NOT NULL
);
"""

ALL_CREATE_TABLES = [
    CREATE_PIPELINE_RUNS,
    CREATE_STAGE_RESULTS,
    CREATE_WEBHOOK_CONFIGS,
    CREATE_WEBHOOK_LOGS,
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineRun:
    id: str
    work_id: str
    task_path: str
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    current_stage: str | None = None
    config_json: str | None = None


@dataclass
class StageResult:
    id: int | None
    run_id: str
    stage_name: str
    status: str
    result_json: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class WebhookConfig:
    id: int | None
    name: str
    url: str
    events: str = "[]"
    active: bool = True
    created_at: str = field(default_factory=_now_iso)


@dataclass
class WebhookLog:
    id: int | None
    config_id: int
    event: str
    status_code: int | None = None
    response: str | None = None
    sent_at: str = field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# CRUD helpers  (all accept an aiosqlite Connection)
# ---------------------------------------------------------------------------

async def insert_pipeline_run(db, run: PipelineRun) -> None:
    await db.execute(
        "INSERT INTO pipeline_runs (id, work_id, task_path, status, started_at, finished_at, current_stage, config_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run.id, run.work_id, run.task_path, run.status,
         run.started_at, run.finished_at, run.current_stage, run.config_json),
    )
    await db.commit()


async def get_pipeline_run(db, run_id: str) -> PipelineRun | None:
    cursor = await db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return PipelineRun(*row)


async def list_pipeline_runs(db, *, limit: int = 50, offset: int = 0) -> list[PipelineRun]:
    cursor = await db.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    return [PipelineRun(*r) for r in rows]


async def update_pipeline_run_status(db, run_id: str, status: str, **kwargs: Any) -> None:
    sets = ["status = ?"]
    vals: list[Any] = [status]
    for col in ("finished_at", "current_stage"):
        if col in kwargs:
            sets.append(f"{col} = ?")
            vals.append(kwargs[col])
    vals.append(run_id)
    await db.execute(
        f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE id = ?", vals,
    )
    await db.commit()


async def insert_stage_result(db, result: StageResult) -> int:
    cursor = await db.execute(
        "INSERT INTO stage_results (run_id, stage_name, status, result_json, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (result.run_id, result.stage_name, result.status,
         result.result_json, result.started_at, result.finished_at),
    )
    await db.commit()
    return cursor.lastrowid


async def list_stage_results(db, run_id: str) -> list[StageResult]:
    cursor = await db.execute(
        "SELECT * FROM stage_results WHERE run_id = ? ORDER BY id", (run_id,),
    )
    rows = await cursor.fetchall()
    return [StageResult(*r) for r in rows]


async def insert_webhook_config(db, cfg: WebhookConfig) -> int:
    cursor = await db.execute(
        "INSERT INTO webhook_configs (name, url, events, active, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (cfg.name, cfg.url, cfg.events, cfg.active, cfg.created_at),
    )
    await db.commit()
    return cursor.lastrowid


async def list_webhook_configs(db, *, active_only: bool = False) -> list[WebhookConfig]:
    q = "SELECT * FROM webhook_configs"
    params: tuple = ()
    if active_only:
        q += " WHERE active = 1"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [WebhookConfig(*r) for r in rows]


async def insert_webhook_log(db, log: WebhookLog) -> int:
    cursor = await db.execute(
        "INSERT INTO webhook_logs (config_id, event, status_code, response, sent_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (log.config_id, log.event, log.status_code, log.response, log.sent_at),
    )
    await db.commit()
    return cursor.lastrowid


async def list_webhook_logs(db, *, config_id: int | None = None, limit: int = 100) -> list[WebhookLog]:
    q = "SELECT * FROM webhook_logs"
    params: list[Any] = []
    if config_id is not None:
        q += " WHERE config_id = ?"
        params.append(config_id)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [WebhookLog(*r) for r in rows]
