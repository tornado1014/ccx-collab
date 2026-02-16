"""SQLite async database connection for the web dashboard."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from cc_collab.web.models import ALL_CREATE_TABLES

DB_PATH = Path.home() / ".cc-collab" / "dashboard.db"

_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return the shared database connection, opening it if needed."""
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = await aiosqlite.connect(str(DB_PATH))
        _connection.row_factory = aiosqlite.Row
    return _connection


async def init_db() -> None:
    """Create tables if they don't exist."""
    db = await get_db()
    for stmt in ALL_CREATE_TABLES:
        await db.execute(stmt)
    await db.commit()


async def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
