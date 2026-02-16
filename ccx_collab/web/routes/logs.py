"""Log viewer routes with SSE streaming."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["logs"])

# In-memory log buffer (most recent 1000 entries)
_log_buffer: deque = deque(maxlen=1000)


class WebLogHandler(logging.Handler):
    """Captures log messages into an in-memory buffer for web display."""

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "level": record.levelname,
            "message": self.format(record),
            "timestamp": record.created,
            "logger": record.name,
        }
        _log_buffer.append(entry)


def setup_web_logging() -> None:
    """Install the web log handler on the root ccx_collab logger."""
    handler = WebLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger("ccx_collab").addHandler(handler)


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Log viewer page."""
    from ccx_collab.web.app import templates
    return templates.TemplateResponse(request, "logs.html", {})


@router.get("/api/logs")
async def get_logs(limit: int = 100, level: str = ""):
    """Return recent log entries."""
    entries = list(_log_buffer)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    return {"logs": entries[-limit:], "total": len(_log_buffer)}


@router.get("/api/logs/stream")
async def stream_logs():
    """SSE stream for real-time log entries."""
    import json

    async def event_generator() -> AsyncGenerator[str, None]:
        last_idx = len(_log_buffer)
        while True:
            current_len = len(_log_buffer)
            if current_len > last_idx:
                new_entries = list(_log_buffer)[last_idx:]
                for entry in new_entries:
                    yield f"event: log\ndata: {json.dumps(entry)}\n\n"
                last_idx = current_len
            else:
                yield "event: ping\ndata: {}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
