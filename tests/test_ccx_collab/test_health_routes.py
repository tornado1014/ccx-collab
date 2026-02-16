"""Tests for health check routes."""
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


class TestHealthRoutes:
    async def test_health_page(self, client):
        resp = await client.get("/settings/health")
        assert resp.status_code == 200

    async def test_health_api(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "python_version" in data
        assert "ccx_collab_version" in data
        assert "disk_usage" in data
        assert "platform" in data

    async def test_health_cli_detection(self, client):
        resp = await client.get("/api/health")
        data = resp.json()
        assert "claude_code" in data
        assert "codex_cli" in data
        assert "available" in data["claude_code"]
        assert "version" in data["claude_code"]

    async def test_health_storage_info(self, client):
        resp = await client.get("/api/health")
        data = resp.json()
        assert "db_size" in data
        assert "results_count" in data
        assert "db_path" in data
