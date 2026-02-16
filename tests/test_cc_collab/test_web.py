"""Tests for the web dashboard routes and components."""
from __future__ import annotations

import json

import pytest

import cc_collab.web.db as db_module
from cc_collab.web.models import (
    PipelineRun,
    StageResult,
    WebhookConfig,
    _now_iso,
    insert_pipeline_run,
    insert_stage_result,
    insert_webhook_config,
    list_pipeline_runs,
    list_stage_results,
    list_webhook_configs,
    get_pipeline_run,
    update_pipeline_run_status,
)
from cc_collab.web.i18n import get_text, get_locale_from_request, _translations
from cc_collab.web.sse import SSEManager


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def test_db(tmp_path):
    """Use a temporary database for every test."""
    db_module.DB_PATH = tmp_path / "test_dashboard.db"
    db_module._connection = None
    await db_module.init_db()
    yield
    await db_module.close_db()


# ---------------------------------------------------------------------------
# Model CRUD tests
# ---------------------------------------------------------------------------

class TestPipelineRunCRUD:
    async def test_insert_and_get(self):
        db = await db_module.get_db()
        run = PipelineRun(
            id="r1", work_id="w1", task_path="/tmp/t.json",
            status="pending", started_at=_now_iso(),
        )
        await insert_pipeline_run(db, run)
        fetched = await get_pipeline_run(db, "r1")
        assert fetched is not None
        assert fetched.work_id == "w1"

    async def test_list_runs(self):
        db = await db_module.get_db()
        for i in range(3):
            run = PipelineRun(
                id=f"r{i}", work_id=f"w{i}", task_path="/tmp/t.json",
                status="completed", started_at=_now_iso(),
            )
            await insert_pipeline_run(db, run)
        runs = await list_pipeline_runs(db, limit=10)
        assert len(runs) == 3

    async def test_update_status(self):
        db = await db_module.get_db()
        run = PipelineRun(
            id="r-upd", work_id="w-upd", task_path="/tmp/t.json",
            status="running", started_at=_now_iso(),
        )
        await insert_pipeline_run(db, run)
        await update_pipeline_run_status(
            db, "r-upd", "completed", finished_at=_now_iso(),
        )
        fetched = await get_pipeline_run(db, "r-upd")
        assert fetched.status == "completed"
        assert fetched.finished_at is not None

    async def test_get_nonexistent(self):
        db = await db_module.get_db()
        assert await get_pipeline_run(db, "nonexistent") is None


class TestStageResultCRUD:
    async def test_insert_and_list(self):
        db = await db_module.get_db()
        run = PipelineRun(
            id="sr-run", work_id="sr-w", task_path="/tmp/t.json",
            status="running", started_at=_now_iso(),
        )
        await insert_pipeline_run(db, run)

        stage = StageResult(
            id=None, run_id="sr-run", stage_name="validate",
            status="completed", started_at=_now_iso(), finished_at=_now_iso(),
        )
        row_id = await insert_stage_result(db, stage)
        assert row_id > 0

        stages = await list_stage_results(db, "sr-run")
        assert len(stages) == 1
        assert stages[0].stage_name == "validate"


class TestWebhookConfigCRUD:
    async def test_insert_and_list(self):
        db = await db_module.get_db()
        cfg = WebhookConfig(
            id=None, name="Test Slack", url="https://hooks.slack.com/xxx",
            events='["pipeline_completed"]', active=True, created_at=_now_iso(),
        )
        wh_id = await insert_webhook_config(db, cfg)
        assert wh_id > 0

        configs = await list_webhook_configs(db)
        assert len(configs) == 1
        assert configs[0].name == "Test Slack"

    async def test_active_only_filter(self):
        db = await db_module.get_db()
        for i, active in enumerate([True, False, True]):
            cfg = WebhookConfig(
                id=None, name=f"WH{i}", url=f"https://example.com/{i}",
                events="[]", active=active, created_at=_now_iso(),
            )
            await insert_webhook_config(db, cfg)
        active_configs = await list_webhook_configs(db, active_only=True)
        assert len(active_configs) == 2


# ---------------------------------------------------------------------------
# SSE Manager tests
# ---------------------------------------------------------------------------

class TestSSEManager:
    async def test_subscribe_and_publish(self):
        mgr = SSEManager()
        queue = mgr.subscribe("test-work")
        await mgr.publish("test-work", "stage_update", {"stage": "validate"})
        msg = await queue.get()
        assert msg["event"] == "stage_update"
        data = json.loads(msg["data"])
        assert data["stage"] == "validate"

    async def test_unsubscribe(self):
        mgr = SSEManager()
        queue = mgr.subscribe("w1")
        mgr.unsubscribe("w1", queue)
        # Publishing after unsubscribe should not put anything in queue
        await mgr.publish("w1", "test", {})
        assert queue.empty()

    async def test_multiple_subscribers(self):
        mgr = SSEManager()
        q1 = mgr.subscribe("w1")
        q2 = mgr.subscribe("w1")
        await mgr.publish("w1", "ping", {})
        assert not q1.empty()
        assert not q2.empty()

    async def test_publish_stage_update(self):
        mgr = SSEManager()
        queue = mgr.subscribe("w2")
        await mgr.publish_stage_update("w2", "plan", "running", detail="Planning...")
        msg = await queue.get()
        data = json.loads(msg["data"])
        assert data["stage"] == "plan"
        assert data["status"] == "running"
        assert data["detail"] == "Planning..."

    async def test_publish_pipeline_complete(self):
        mgr = SSEManager()
        queue = mgr.subscribe("w3")
        await mgr.publish_pipeline_complete("w3", "completed")
        msg = await queue.get()
        assert msg["event"] == "pipeline_complete"

    async def test_publish_to_nonexistent_work_id(self):
        mgr = SSEManager()
        # Should not raise
        await mgr.publish("nonexistent", "test", {})


# ---------------------------------------------------------------------------
# i18n tests
# ---------------------------------------------------------------------------

class TestI18n:
    def setup_method(self):
        _translations.clear()

    def test_english_translation(self):
        text = get_text("dashboard", "en")
        assert text == "Dashboard"

    def test_korean_translation(self):
        text = get_text("dashboard", "ko")
        assert text in ("Dashboard", "\ub300\uc2dc\ubcf4\ub4dc")  # either works

    def test_fallback_to_key(self):
        text = get_text("nonexistent_key_xyz", "en")
        assert text == "nonexistent_key_xyz"

    def test_fallback_to_english(self):
        # A key that exists in English but not in Korean should fall back
        text = get_text("dashboard", "ko")
        assert text  # Should return something, not empty

    def test_locale_from_request_query_param(self):
        class MockRequest:
            query_params = {"lang": "ko"}
            cookies = {}
        assert get_locale_from_request(MockRequest()) == "ko"

    def test_locale_from_request_cookie(self):
        class MockRequest:
            query_params = {}
            cookies = {"lang": "ko"}
        assert get_locale_from_request(MockRequest()) == "ko"

    def test_locale_from_request_default(self):
        class MockRequest:
            query_params = {}
            cookies = {}
        assert get_locale_from_request(MockRequest()) == "en"

    def test_locale_invalid_falls_back(self):
        class MockRequest:
            query_params = {"lang": "fr"}
            cookies = {}
        assert get_locale_from_request(MockRequest()) == "en"


# ---------------------------------------------------------------------------
# FastAPI route integration tests (using httpx AsyncClient)
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """Create httpx AsyncClient for the FastAPI app."""
    from httpx import ASGITransport, AsyncClient
    from cc_collab.web.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRouteIntegration:
    async def test_dashboard(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_tasks_page(self, client):
        resp = await client.get("/tasks")
        assert resp.status_code == 200

    async def test_tasks_create_page(self, client):
        resp = await client.get("/tasks/create")
        assert resp.status_code == 200

    async def test_history_page(self, client):
        resp = await client.get("/history")
        assert resp.status_code == 200

    async def test_history_charts(self, client):
        resp = await client.get("/history/charts")
        assert resp.status_code == 200

    async def test_history_stats_api(self, client):
        resp = await client.get("/api/history/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "status_counts" in data
        assert "total_runs" in data

    async def test_webhooks_page(self, client):
        resp = await client.get("/settings/webhooks")
        assert resp.status_code == 200

    async def test_task_not_found(self, client):
        resp = await client.get("/tasks/nonexistent-999")
        assert resp.status_code == 404
