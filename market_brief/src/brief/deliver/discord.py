from __future__ import annotations

import logging
import os

import httpx

from brief.render import split_telegram_messages

logger = logging.getLogger(__name__)

# Discord webhook content limit (leave headroom below 2000)
_DISCORD_CONTENT_LIMIT = 1900


def discord_configured() -> bool:
    return bool(os.environ.get("DISCORD_WEBHOOK_URL"))


def html_to_discord_markdown(html: str) -> str:
    """Loose HTML → Discord-flavored markdown for webhook posts."""
    plain = html.replace("<b>", "**").replace("</b>", "**").replace("<i>", "*").replace("</i>", "*")
    plain = plain.replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "")
    plain = plain.replace("<pre>", "```").replace("</pre>", "```")
    return plain


def send_discord(html: str, *, client: httpx.Client | None = None) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    plain = html_to_discord_markdown(html)
    parts = split_telegram_messages(plain, limit=_DISCORD_CONTENT_LIMIT)
    owns = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        for idx, part in enumerate(parts, start=1):
            resp = http.post(url, json={"content": part})
            resp.raise_for_status()
            if len(parts) > 1:
                logger.info("Discord webhook part %s/%s posted", idx, len(parts))
    finally:
        if owns:
            http.close()
