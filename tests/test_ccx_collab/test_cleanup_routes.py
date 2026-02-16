"""Tests for cleanup routes."""
from __future__ import annotations

import os
import time

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


class TestCleanupRoutes:
    async def test_cleanup_page(self, client):
        resp = await client.get("/settings/cleanup")
        assert resp.status_code == 200

    async def test_cleanup_preview(self, client, tmp_path, monkeypatch):
        # Patch project root to allow tmp_path through path traversal check
        monkeypatch.setattr(
            "ccx_collab.web.routes.cleanup.get_project_root", lambda: tmp_path
        )
        old_file = tmp_path / "old_result.json"
        old_file.write_text("{}")
        os.utime(str(old_file), (time.time() - 86400 * 60, time.time() - 86400 * 60))

        resp = await client.post("/api/cleanup/preview", json={
            "results_dir": str(tmp_path),
            "retention_days": 30,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert "total_size" in data
        assert data["deleted_count"] >= 1
        assert data["dry_run"] is True
        assert old_file.exists()

    async def test_cleanup_execute(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ccx_collab.web.routes.cleanup.get_project_root", lambda: tmp_path
        )
        old_file = tmp_path / "old_result.json"
        old_file.write_text("{}")
        os.utime(str(old_file), (time.time() - 86400 * 60, time.time() - 86400 * 60))

        resp = await client.post("/api/cleanup/execute", json={
            "results_dir": str(tmp_path),
            "retention_days": 30,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] >= 1
        assert data["dry_run"] is False
        assert not old_file.exists()

    async def test_cleanup_no_old_files(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ccx_collab.web.routes.cleanup.get_project_root", lambda: tmp_path
        )
        new_file = tmp_path / "new_result.json"
        new_file.write_text("{}")
        resp = await client.post("/api/cleanup/preview", json={
            "results_dir": str(tmp_path),
            "retention_days": 30,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 0
