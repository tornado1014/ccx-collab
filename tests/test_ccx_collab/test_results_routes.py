"""Tests for result browser routes."""
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


class TestResultsBrowser:
    async def test_results_page(self, client):
        resp = await client.get("/results")
        assert resp.status_code == 200

    async def test_results_api(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccx_collab.web.routes.results.get_results_dir", lambda w="": tmp_path)
        (tmp_path / "plan_abc123.json").write_text('{"status":"passed"}')
        resp = await client.get("/api/results")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "plan_abc123.json"

    async def test_result_file_content(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccx_collab.web.routes.results.get_results_dir", lambda w="": tmp_path)
        (tmp_path / "plan_abc123.json").write_text('{"status":"passed"}')
        resp = await client.get("/api/results/plan_abc123.json")
        assert resp.status_code == 200
        assert resp.json()["status"] == "passed"

    async def test_path_traversal_blocked(self, client):
        resp = await client.get("/api/results/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)

    async def test_path_traversal_dotdot(self, client):
        resp = await client.get("/api/results/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    async def test_results_filter(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccx_collab.web.routes.results.get_results_dir", lambda w="": tmp_path)
        (tmp_path / "plan_abc123.json").write_text('{}')
        (tmp_path / "plan_xyz789.json").write_text('{}')
        resp = await client.get("/api/results?work_id=abc123")
        data = resp.json()
        assert len(data["files"]) == 1
