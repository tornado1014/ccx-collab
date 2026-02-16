"""Tests for webhook sending logic."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ccx_collab.web.webhook import (
    _detect_webhook_type,
    _format_discord_message,
    _format_generic_message,
    _format_slack_message,
    send_webhook,
)


class TestWebhookTypeDetection:
    def test_detect_slack(self):
        assert _detect_webhook_type("https://hooks.slack.com/services/xxx") == "slack"

    def test_detect_slack_alt(self):
        assert _detect_webhook_type("https://slack.com/webhook/xxx") == "slack"

    def test_detect_discord(self):
        assert _detect_webhook_type("https://discord.com/api/webhooks/xxx") == "discord"

    def test_detect_discord_alt(self):
        assert _detect_webhook_type("https://discordapp.com/api/webhooks/xxx") == "discord"

    def test_detect_generic(self):
        assert _detect_webhook_type("https://example.com/webhook") == "generic"

    def test_detect_generic_localhost(self):
        assert _detect_webhook_type("http://localhost:3000/hook") == "generic"


class TestSlackFormat:
    def test_basic_format(self):
        msg = _format_slack_message("pipeline_completed", {"work_id": "abc123"})
        assert "text" in msg
        assert "blocks" in msg
        assert "ccx-collab" in msg["text"]

    def test_has_header_block(self):
        msg = _format_slack_message("pipeline_started", {})
        assert msg["blocks"][0]["type"] == "header"

    def test_emoji_mapping(self):
        for event in ["pipeline_started", "stage_completed", "pipeline_completed", "pipeline_failed"]:
            msg = _format_slack_message(event, {})
            assert ":" in msg["text"]  # has emoji

    def test_includes_work_id(self):
        msg = _format_slack_message("pipeline_completed", {"work_id": "test-id"})
        found = any("test-id" in str(b) for b in msg["blocks"])
        assert found

    def test_includes_stage_info(self):
        msg = _format_slack_message("stage_completed", {"stage": "verify", "status": "passed"})
        found = any("verify" in str(b) for b in msg["blocks"])
        assert found


class TestDiscordFormat:
    def test_basic_format(self):
        msg = _format_discord_message("pipeline_failed", {"work_id": "xyz"})
        assert "embeds" in msg
        assert "content" in msg
        assert len(msg["embeds"]) == 1

    def test_color_mapping(self):
        assert _format_discord_message("pipeline_failed", {})["embeds"][0]["color"] == 0xE74C3C
        assert _format_discord_message("pipeline_completed", {})["embeds"][0]["color"] == 0x2ECC71
        assert _format_discord_message("pipeline_started", {})["embeds"][0]["color"] == 0x3498DB

    def test_has_timestamp(self):
        msg = _format_discord_message("pipeline_started", {})
        assert "timestamp" in msg["embeds"][0]

    def test_includes_fields(self):
        msg = _format_discord_message("stage_completed", {"work_id": "w1", "stage": "plan"})
        fields = msg["embeds"][0]["fields"]
        assert len(fields) >= 2


class TestGenericFormat:
    def test_basic_format(self):
        msg = _format_generic_message("stage_completed", {"stage": "verify"})
        assert msg["event"] == "stage_completed"
        assert msg["source"] == "ccx-collab"
        assert "timestamp" in msg
        assert msg["data"]["stage"] == "verify"

    def test_empty_data(self):
        msg = _format_generic_message("test", {})
        assert msg["data"] == {}


class TestSendWebhook:
    @pytest.mark.asyncio
    async def test_send_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("ccx_collab.web.webhook.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_cls.return_value = mock_client

            status, response = await send_webhook(
                "https://example.com/hook", "test", {"msg": "hello"}
            )
            assert status == 200
            assert response == "ok"

    @pytest.mark.asyncio
    async def test_send_error(self):
        import httpx

        with patch("ccx_collab.web.webhook.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            status, response = await send_webhook(
                "https://bad-url.example.com", "test", {}
            )
            assert status == 0
            assert "Connection refused" in response

    @pytest.mark.asyncio
    async def test_send_routes_to_slack(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("ccx_collab.web.webhook.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_cls.return_value = mock_client

            await send_webhook(
                "https://hooks.slack.com/services/T/B/xxx", "pipeline_completed", {}
            )
            # Verify post was called with Slack-formatted payload
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "blocks" in payload
