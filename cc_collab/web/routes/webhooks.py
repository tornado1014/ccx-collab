"""Webhook settings routes."""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.get("/settings/webhooks", response_class=HTMLResponse)
async def webhooks_page(request: Request):
    """Webhook settings page."""
    from cc_collab.web.app import templates
    from cc_collab.web.db import get_db
    from cc_collab.web.models import list_webhook_configs

    db = await get_db()
    configs = await list_webhook_configs(db)

    # Add parsed events list for template rendering
    webhooks = []
    for cfg in configs:
        wh = {"id": cfg.id, "name": cfg.name, "url": cfg.url,
              "active": cfg.active, "created_at": cfg.created_at}
        try:
            wh["events_list"] = json.loads(cfg.events) if isinstance(cfg.events, str) else cfg.events
        except (json.JSONDecodeError, TypeError):
            wh["events_list"] = []
        webhooks.append(wh)

    return templates.TemplateResponse("settings/webhooks.html", {
        "request": request,
        "webhooks": webhooks,
    })


@router.post("/api/webhooks")
async def create_webhook(
    name: str = Form(...),
    url: str = Form(...),
    events: list[str] = Form(default=[]),
):
    """Create a new webhook configuration."""
    from cc_collab.web.db import get_db
    from cc_collab.web.models import WebhookConfig, insert_webhook_config, _now_iso

    db = await get_db()
    config = WebhookConfig(
        id=None,
        name=name,
        url=url,
        events=json.dumps(events),
        active=True,
        created_at=_now_iso(),
    )
    webhook_id = await insert_webhook_config(db, config)
    return HTMLResponse(f'<p>Webhook "{name}" created (ID: {webhook_id}).</p><script>location.reload()</script>')


@router.put("/api/webhooks/{webhook_id}")
async def update_webhook(webhook_id: int, active: bool = True):
    """Toggle webhook active status."""
    from cc_collab.web.db import get_db
    db = await get_db()
    await db.execute("UPDATE webhook_configs SET active = ? WHERE id = ?", (active, webhook_id))
    await db.commit()
    return HTMLResponse(f'<p>Webhook updated.</p><script>location.reload()</script>')


@router.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int):
    """Delete a webhook configuration."""
    from cc_collab.web.db import get_db
    db = await get_db()
    await db.execute("DELETE FROM webhook_configs WHERE id = ?", (webhook_id,))
    await db.commit()
    return HTMLResponse("")


@router.post("/api/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: int):
    """Send a test webhook notification."""
    from cc_collab.web.db import get_db
    from cc_collab.web.models import list_webhook_configs
    from cc_collab.web.webhook import send_webhook

    db = await get_db()
    configs = await list_webhook_configs(db)
    config = next((c for c in configs if c.id == webhook_id), None)
    if config is None:
        return HTMLResponse("<small>Webhook not found</small>", status_code=404)

    status_code, response = await send_webhook(
        config.url, "test", {"message": "Test webhook from cc-collab dashboard"}
    )

    if 200 <= status_code < 300:
        return HTMLResponse(f'<small style="color: green">OK ({status_code})</small>')
    else:
        return HTMLResponse(f'<small style="color: red">Failed ({status_code})</small>')
