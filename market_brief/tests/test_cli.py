from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from brief.cli import cmd_run

ROOT = Path(__file__).resolve().parents[1]


def test_cmd_run_dry_run(monkeypatch, tmp_path, fixture_inject, fixed_now) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BRIEF_DATA_DIR", str(tmp_path))
    args = Namespace(
        dry_run=True,
        no_llm=True,
        force=False,
        deliver="none",
        skip_window_check=True,
        orbis_html=False,
    )
    from brief import cli, pipeline

    def _build(**kwargs):  # type: ignore[no-untyped-def]
        return pipeline.build_brief(
            use_llm=False,
            thresholds_path=ROOT / "config" / "thresholds.yaml",
            events_path=ROOT / "config" / "events.yaml",
            inject=fixture_inject,
            when=fixed_now,
        )

    with patch.object(cli, "build_brief", side_effect=_build):
        code = cmd_run(args)
    assert code == 0
    assert list(tmp_path.glob("dry_run_*.html"))


def test_cmd_run_auto_delivers_telegram_then_discord(
    monkeypatch, tmp_path, fixture_inject, fixed_now
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BRIEF_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    args = Namespace(
        dry_run=False,
        no_llm=True,
        force=True,
        deliver="auto",
        skip_window_check=True,
        orbis_html=False,
    )
    from brief import cli, pipeline

    def _build(**kwargs):  # type: ignore[no-untyped-def]
        return pipeline.build_brief(
            use_llm=False,
            thresholds_path=ROOT / "config" / "thresholds.yaml",
            events_path=ROOT / "config" / "events.yaml",
            inject=fixture_inject,
            when=fixed_now,
        )

    calls: list[str] = []

    def _tg(html: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        calls.append("telegram")

    def _dc(html: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        calls.append("discord")

    with (
        patch.object(cli, "build_brief", side_effect=_build),
        patch.object(cli, "send_telegram_html", side_effect=_tg),
        patch.object(cli, "send_discord", side_effect=_dc),
    ):
        code = cmd_run(args)
    assert code == 0
    assert calls == ["telegram", "discord"]
