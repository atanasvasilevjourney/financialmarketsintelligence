from __future__ import annotations

from brief.render import split_telegram_messages


def test_split_telegram_under_limit() -> None:
    text = "hello"
    assert split_telegram_messages(text) == [text]


def test_split_telegram_chunks() -> None:
    text = "\n".join(["line"] * 5000)
    parts = split_telegram_messages(text, limit=1000)
    assert len(parts) > 1
    assert all(len(p) <= 1000 for p in parts)
