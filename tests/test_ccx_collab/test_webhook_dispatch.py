"""Tests for webhook dispatch integration."""
from __future__ import annotations

import json
import pytest

import ccx_collab.web.db as db_module
from ccx_collab.web.models import (
    WebhookConfig, insert_webhook_config, list_webhook_logs, _now_iso,
)


@pytest.fixture(autouse=True)
async def test_db(tmp_path):
    db_module.DB_PATH = tmp_path / "test.db"
    db_module._connection = None
    await db_module.init_db()
    yield
    await db_module.close_db()


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    from ccx_collab.web.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestWebhookDispatch:
    async def test_trigger_webhooks_logs_delivery(self):
        """Webhook trigger should log delivery attempt."""
        db = await db_module.get_db()
        await insert_webhook_config(db, WebhookConfig(
            id=None, name="test", url="https://httpbin.org/post",
            events='["stage_completed"]', active=True, created_at=_now_iso(),
        ))
        from ccx_collab.web.webhook import trigger_webhooks
        await trigger_webhooks("stage_completed", {"work_id": "w1", "stage": "validate"})
        logs = await list_webhook_logs(db)
        assert len(logs) >= 1
        assert logs[0].event == "stage_completed"

    async def test_webhook_event_filter(self):
        """Events not subscribed should be filtered out."""
        db = await db_module.get_db()
        await insert_webhook_config(db, WebhookConfig(
            id=None, name="test", url="https://httpbin.org/post",
            events='["pipeline_completed"]', active=True, created_at=_now_iso(),
        ))
        from ccx_collab.web.webhook import trigger_webhooks
        await trigger_webhooks("stage_completed", {"work_id": "w1"})
        logs = await list_webhook_logs(db)
        assert len(logs) == 0

    async def test_webhook_logs_page(self, client):
        resp = await client.get("/settings/webhooks/logs")
        assert resp.status_code == 200
