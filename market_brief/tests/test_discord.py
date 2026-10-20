from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from brief.deliver.discord import html_to_discord_markdown, send_discord


def test_html_to_discord_markdown() -> None:
    out = html_to_discord_markdown("<b>Hi</b><ul><li>one</li></ul>")
    assert "**Hi**" in out
    assert "- one" in out


def test_send_discord_posts_webhook(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    client = MagicMock(spec=httpx.Client)
    client.post.return_value = mock_resp

    send_discord("<b>Brief</b>", client=client)

    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == "https://discord.test/webhook"
    assert kwargs["json"]["content"] == "**Brief**"


def test_send_discord_splits_long_content(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    client = MagicMock(spec=httpx.Client)
    client.post.return_value = mock_resp

    send_discord("x" * 2500, client=client)

    assert client.post.call_count == 2
