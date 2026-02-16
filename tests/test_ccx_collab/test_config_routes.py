"""Tests for configuration management routes."""
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


class TestConfigRoutes:
    async def test_config_page(self, client):
        resp = await client.get("/settings/config")
        assert resp.status_code == 200

    async def test_merged_config(self, client):
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "results_dir" in data
        assert "retention_days" in data

    async def test_config_layers(self, client):
        resp = await client.get("/api/config/layers")
        assert resp.status_code == 200
        data = resp.json()
        assert "defaults" in data
        assert "user" in data
        assert "project" in data
        assert "merged" in data

    async def test_env_vars(self, client):
        resp = await client.get("/api/config/env")
        assert resp.status_code == 200
        data = resp.json()
        assert "CLAUDE_CODE_CMD" in data
        assert "SIMULATE_AGENTS" in data

    async def test_save_project_config(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ccx_collab.web.routes.config.get_project_root", lambda: tmp_path
        )
        resp = await client.put("/api/config/project", json={
            "content": "results_dir: custom/path\nretention_days: 7\n"
        })
        assert resp.status_code == 200
        saved = (tmp_path / ".ccx-collab.yaml").read_text()
        assert "retention_days: 7" in saved

    async def test_save_invalid_yaml(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ccx_collab.web.routes.config.get_project_root", lambda: tmp_path
        )
        resp = await client.put("/api/config/project", json={
            "content": "invalid: yaml: [["
        })
        assert resp.status_code == 400
