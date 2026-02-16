"""Webhook sending logic for pipeline events."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


def _format_slack_message(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Slack webhook payload."""
    emoji_map = {
        "pipeline_started": ":rocket:",
        "stage_completed": ":white_check_mark:",
        "pipeline_completed": ":tada:",
        "pipeline_failed": ":x:",
    }
    emoji = emoji_map.get(event, ":bell:")
    text = f"{emoji} *ccx-collab*: {event.replace('_', ' ').title()}"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"ccx-collab: {event.replace('_', ' ').title()}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Event:* {event}\n*Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"}},
    ]

    if data.get("work_id"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Work ID:* {data['work_id']}"}})
    if data.get("stage"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Stage:* {data['stage']} ({data.get('status', 'unknown')})"}})

    return {"text": text, "blocks": blocks}


def _format_discord_message(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Discord webhook payload."""
    color_map = {
        "pipeline_started": 0x3498DB,
        "stage_completed": 0x2ECC71,
        "pipeline_completed": 0x2ECC71,
        "pipeline_failed": 0xE74C3C,
    }

    embed = {
        "title": f"ccx-collab: {event.replace('_', ' ').title()}",
        "color": color_map.get(event, 0x95A5A6),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": [{"name": "Event", "value": event, "inline": True}],
    }

    if data.get("work_id"):
        embed["fields"].append({"name": "Work ID", "value": data["work_id"], "inline": True})
    if data.get("stage"):
        embed["fields"].append({"name": "Stage", "value": f"{data['stage']} ({data.get('status', '')})", "inline": True})

    return {"content": f"ccx-collab: {event}", "embeds": [embed]}


def _format_generic_message(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Format a generic JSON webhook payload."""
    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "source": "ccx-collab",
    }


def _detect_webhook_type(url: str) -> str:
    """Detect webhook type from URL."""
    if "slack.com" in url or "hooks.slack.com" in url:
        return "slack"
    if "discord.com" in url or "discordapp.com" in url:
        return "discord"
    return "generic"


async def send_webhook(url: str, event: str, data: Dict[str, Any]) -> tuple[int, str]:
    """Send a webhook notification. Returns (status_code, response_text)."""
    webhook_type = _detect_webhook_type(url)

    if webhook_type == "slack":
        payload = _format_slack_message(event, data)
    elif webhook_type == "discord":
        payload = _format_discord_message(event, data)
    else:
        payload = _format_generic_message(event, data)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            logger.info("Webhook sent to %s: status=%d", url[:50], response.status_code)
            return response.status_code, response.text[:500]
    except httpx.HTTPError as exc:
        logger.error("Webhook send failed for %s: %s", url[:50], exc)
        return 0, str(exc)[:500]


async def trigger_webhooks(event: str, data: Dict[str, Any]) -> None:
    """Trigger all active webhooks for the given event."""
    from ccx_collab.web.db import get_db
    from ccx_collab.web.models import (
        list_webhook_configs, insert_webhook_log, WebhookLog, _now_iso,
    )

    db = await get_db()
    configs = await list_webhook_configs(db, active_only=True)

    for config in configs:
        events = json.loads(config.events) if isinstance(config.events, str) else config.events
        if event not in events:
            continue

        status_code, response_text = await send_webhook(config.url, event, data)

        log = WebhookLog(
            id=None,
            config_id=config.id,
            event=event,
            status_code=status_code,
            response=response_text,
            sent_at=_now_iso(),
        )
        await insert_webhook_log(db, log)
