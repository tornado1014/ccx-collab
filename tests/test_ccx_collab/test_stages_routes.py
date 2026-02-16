"""Tests for stage execution routes."""
from __future__ import annotations

import pytest

import ccx_collab.web.db as db_module


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


class TestStagesPage:
    async def test_stages_index(self, client):
        resp = await client.get("/stages")
        assert resp.status_code == 200
        assert "validate" in resp.text.lower()
        assert "plan" in resp.text.lower()
        assert "implement" in resp.text.lower()

    async def test_stage_run_page(self, client):
        resp = await client.get("/stages/validate")
        assert resp.status_code == 200
        assert "Task File" in resp.text

    async def test_stage_run_page_unknown(self, client):
        resp = await client.get("/stages/nonexistent")
        assert resp.status_code == 404

    async def test_stage_form_data(self, client):
        resp = await client.get("/api/stages/validate/form")
        assert resp.status_code == 200
        data = resp.json()
        assert "fields" in data
        assert "description" in data
        assert "available_files" in data

    async def test_stage_form_unknown(self, client):
        resp = await client.get("/api/stages/nonexistent/form")
        assert resp.status_code == 404

    async def test_run_unknown_stage(self, client):
        resp = await client.post("/api/stages/nonexistent/run", json={"simulate": True, "params": {}})
        assert resp.status_code == 404

    async def test_run_validate_simulate(self, client, tmp_path):
        task_file = tmp_path / "test.task.json"
        task_file.write_text('{"task_id":"t1","title":"test","scope":"test","acceptance_criteria":[],"subtasks":[]}')
        resp = await client.post("/api/stages/validate/run", json={
            "simulate": True,
            "params": {"task_path": str(task_file), "work_id": "test-wid"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "validate"
        assert "exit_code" in data
        assert "status" in data

    async def test_all_stages_listed(self, client):
        resp = await client.get("/stages")
        assert resp.status_code == 200
        for stage in ["validate", "plan", "split", "implement", "merge", "verify", "review", "retrospect"]:
            assert stage in resp.text.lower()
