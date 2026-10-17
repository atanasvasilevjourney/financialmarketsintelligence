from __future__ import annotations

import os

import httpx


def discord_configured() -> bool:
    return bool(os.environ.get("DISCORD_WEBHOOK_URL"))


def send_discord(html: str, *, client: httpx.Client | None = None) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    owns = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        # Discord: strip tags loosely for webhook simplicity
        plain = html.replace("<b>", "**").replace("</b>", "**").replace("<i>", "*").replace("</i>", "*")
        plain = plain.replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "")
        plain = plain.replace("<pre>", "```").replace("</pre>", "```")
        resp = http.post(url, json={"content": plain[:1900]})
        resp.raise_for_status()
    finally:
        if owns:
            http.close()
