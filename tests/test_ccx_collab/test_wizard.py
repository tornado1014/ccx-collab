"""Tests for guided wizard workflow."""
from __future__ import annotations

import pytest

import ccx_collab.web.db as db_module
from ccx_collab.web.models import (
    PipelineRun,
    insert_pipeline_run,
)


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def test_db(tmp_path):
    db_module.DB_PATH = tmp_path / "test_wizard.db"
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


# ---------------------------------------------------------------------------
# Task 0: stop_after_stage tests
# ---------------------------------------------------------------------------


class TestStopAfterStage:
    async def test_pipeline_accepts_stop_after_stage(self, client, tmp_path):
        """stop_after_stage parameter is accepted by the pipeline API."""
        task_file = tmp_path / "test.task.json"
        task_file.write_text('{"task_id":"t1","title":"test"}')
        resp = await client.post(
            "/api/pipeline/run",
            json={
                "task_path": str(task_file),
                "simulate": True,
                "stop_after_stage": "plan",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "work_id" in data

    async def test_awaiting_review_status_in_db(self):
        """awaiting_review status can be stored and retrieved."""
        db = await db_module.get_db()
        run = PipelineRun(
            id="r-await",
            work_id="w-await",
            task_path="/tmp/t.json",
            status="awaiting_review",
            current_stage="plan",
        )
        await insert_pipeline_run(db, run)
        from ccx_collab.web.models import get_pipeline_run

        fetched = await get_pipeline_run(db, "r-await")
        assert fetched is not None
        assert fetched.status == "awaiting_review"


# ---------------------------------------------------------------------------
# Task 1: Wizard start tests
# ---------------------------------------------------------------------------


class TestWizardStart:
    async def test_wizard_page(self, client):
        resp = await client.get("/wizard")
        assert resp.status_code == 200
        html = resp.text
        assert "goal" in html.lower() or "describe" in html.lower() or "build" in html.lower()

    async def test_wizard_create_task(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ccx_collab.web.routes.wizard._get_tasks_dir", lambda: tmp_path
        )
        resp = await client.post(
            "/api/wizard/start",
            json={
                "goal": "Add user authentication to the web app",
                "complexity": "standard",
                "simulate": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "work_id" in data
        assert "redirect" in data
        # task file created
        task_files = list(tmp_path.glob("*.task.json"))
        assert len(task_files) >= 1

    async def test_wizard_in_sidebar(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "/wizard" in html


# ---------------------------------------------------------------------------
# Task 2: Plan review tests
# ---------------------------------------------------------------------------


class TestWizardReview:
    async def test_review_page_renders(self, client):
        """Review page renders for an awaiting_review run."""
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r1",
                work_id="w1",
                task_path="/tmp/test.task.json",
                status="awaiting_review",
                current_stage="plan",
            ),
        )
        resp = await client.get("/wizard/r1/review")
        assert resp.status_code == 200
        html = resp.text
        assert "review" in html.lower() or "plan" in html.lower()

    async def test_approve_plan(self, client, tmp_path, monkeypatch):
        """Approving a plan resumes the pipeline."""
        monkeypatch.setattr(
            "ccx_collab.web.routes.wizard._get_tasks_dir", lambda: tmp_path
        )
        task_file = tmp_path / "test.task.json"
        task_file.write_text('{"task_id":"t1","title":"test"}')
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r2",
                work_id="w2",
                task_path=str(task_file),
                status="awaiting_review",
                current_stage="plan",
            ),
        )
        resp = await client.post(
            "/api/wizard/r2/approve", json={"simulate": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resumed"

    async def test_review_page_not_found(self, client):
        resp = await client.get("/wizard/nonexistent/review")
        assert resp.status_code == 404

    async def test_approve_wrong_status(self, client):
        """Cannot approve a run that is not awaiting_review."""
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r-wrong",
                work_id="w-wrong",
                task_path="/tmp/t.json",
                status="running",
                current_stage="plan",
            ),
        )
        resp = await client.post(
            "/api/wizard/r-wrong/approve", json={"simulate": True}
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Task 3: Progress + Done tests
# ---------------------------------------------------------------------------


class TestWizardProgress:
    async def test_progress_page(self, client):
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r3",
                work_id="w3",
                task_path="test.json",
                status="running",
                current_stage="implement",
            ),
        )
        resp = await client.get("/wizard/r3/progress")
        assert resp.status_code == 200
        assert "progress" in resp.text.lower() or "execute" in resp.text.lower() or "building" in resp.text.lower()

    async def test_done_page(self, client):
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r4",
                work_id="w4",
                task_path="test.json",
                status="completed",
                current_stage="review",
            ),
        )
        resp = await client.get("/wizard/r4/done")
        assert resp.status_code == 200

    async def test_progress_shows_completed(self, client):
        """Completed run shows done link on progress page."""
        db = await db_module.get_db()
        await insert_pipeline_run(
            db,
            PipelineRun(
                id="r5",
                work_id="w5",
                task_path="test.json",
                status="completed",
            ),
        )
        resp = await client.get("/wizard/r5/progress")
        assert resp.status_code == 200
        assert "done" in resp.text.lower() or "completed" in resp.text.lower() or "results" in resp.text.lower()


# ---------------------------------------------------------------------------
# Task 4: Dashboard integration tests
# ---------------------------------------------------------------------------


class TestDashboardIntegration:
    async def test_dashboard_has_wizard_link(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "/wizard" in html

    async def test_sidebar_has_new_project(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "New Project" in html or "new_project" in html

    async def test_sidebar_has_advanced_toggle(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "advancedMode" in html


# ---------------------------------------------------------------------------
# Task 5: i18n tests
# ---------------------------------------------------------------------------


class TestWizardI18n:
    def test_stage_labels_exist(self):
        from ccx_collab.web.i18n import get_stage_label

        assert get_stage_label("validate", "en") == "Check Requirements"
        assert get_stage_label("implement", "ko") == "\ucf54\ub4dc \uc791\uc131"

    def test_stage_label_fallback(self):
        from ccx_collab.web.i18n import get_stage_label

        assert get_stage_label("unknown_stage", "en") == "unknown_stage"

    def test_wizard_i18n_keys_in_en(self):
        from ccx_collab.web.i18n import get_text, _translations
        _translations.clear()

        assert get_text("new_project", "en") == "New Project"
        assert get_text("what_to_build", "en") == "What do you want to build?"
        assert get_text("create_plan", "en") == "Create Plan"

    def test_wizard_i18n_keys_in_ko(self):
        from ccx_collab.web.i18n import get_text, _translations
        _translations.clear()

        assert get_text("new_project", "ko") == "\uc0c8 \ud504\ub85c\uc81d\ud2b8"
        assert get_text("create_plan", "ko") == "\uacc4\ud68d \ub9cc\ub4e4\uae30"

    async def test_wizard_page_ko(self, client):
        resp = await client.get("/wizard?lang=ko")
        assert resp.status_code == 200
