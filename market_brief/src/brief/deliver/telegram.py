from __future__ import annotations

import os

import httpx

from brief.render import split_telegram_messages

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send_telegram_html(html: str, *, client: httpx.Client | None = None) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram not configured (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    owns = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        url = TELEGRAM_API.format(token=token)
        for part in split_telegram_messages(html):
            resp = http.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": part,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
    finally:
        if owns:
            http.close()
