"""Tests for log viewer routes."""
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


class TestLogsRoutes:
    async def test_logs_page(self, client):
        resp = await client.get("/logs")
        assert resp.status_code == 200

    async def test_logs_api(self, client):
        resp = await client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total" in data

    async def test_logs_filter(self, client):
        resp = await client.get("/api/logs?level=ERROR")
        assert resp.status_code == 200
