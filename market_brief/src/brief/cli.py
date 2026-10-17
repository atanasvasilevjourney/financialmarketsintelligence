from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from brief.deliver.discord import discord_configured, send_discord
from brief.deliver.telegram import send_telegram_html, telegram_configured
from brief.health import ping_failure, ping_success
from brief.pipeline import build_brief, in_nyse_send_window, is_total_failure, trading_date_now
from brief.render import render_orbis_html, telegram_orbis_summary
from brief.storage import (
    already_sent,
    mark_sent,
    save_snapshot,
    write_dry_run_html,
    write_orbis_html,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("brief")


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="brief", description="Daily market brief")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Collect data, render, optionally deliver")
    run.add_argument("--dry-run", action="store_true", help="No Telegram/Discord; write HTML snapshot")
    run.add_argument("--no-llm", action="store_true", help="Template commentary only")
    run.add_argument("--force", action="store_true", help="Ignore idempotency marker")
    run.add_argument(
        "--deliver",
        choices=("auto", "telegram", "discord", "none"),
        default="auto",
        help="Delivery channel (auto=telegram if configured)",
    )
    run.add_argument(
        "--skip-window-check",
        action="store_true",
        help="Skip NYSE 07:30-08:30 ET guard (for CI/manual)",
    )
    run.add_argument(
        "--orbis-html",
        action="store_true",
        help="Also write ORBIS-branded mobile HTML (JSON-driven; no hardcoded market numbers)",
    )
    return p.parse_args(argv)


def cmd_run(args: argparse.Namespace) -> int:
    root = _package_root()
    thresholds = root / "config" / "thresholds.yaml"
    events = root / "config" / "events.yaml"

    if not args.skip_window_check and not in_nyse_send_window():
        logger.warning("Outside NYSE send window (07:30-08:30 ET); use --skip-window-check to override")

    payload, html = build_brief(
        use_llm=not args.no_llm,
        thresholds_path=thresholds,
        events_path=events,
    )
    td = trading_date_now(payload.generated_at)

    if is_total_failure(payload):
        ping_failure("Total brief failure — insufficient data")
        logger.error("Total failure: no usable inputs")
        print(html)
        return 2

    save_snapshot(payload)

    orbis_path: Path | None = None
    if args.orbis_html:
        orbis_html = render_orbis_html(payload)
        orbis_path = write_orbis_html(td, orbis_html)
        logger.info("ORBIS HTML: %s", orbis_path)

    if args.dry_run:
        path = write_dry_run_html(td, html)
        logger.info("Dry run HTML: %s", path)
        if orbis_path:
            print(orbis_html)
        else:
            print(html)
        ping_success()
        return 0

    if not args.force and already_sent(td):
        logger.info("Already sent for %s; use --force", td)
        print(html)
        return 0

    deliver = args.deliver
    if deliver == "auto":
        deliver = "telegram" if telegram_configured() else "none"

    try:
        if deliver == "telegram":
            if not telegram_configured():
                logger.error("Telegram not configured")
                return 1
            if args.orbis_html and orbis_path:
                send_telegram_html(
                    telegram_orbis_summary(payload, html_path=str(orbis_path))
                )
            else:
                send_telegram_html(html)
        elif deliver == "discord":
            if not discord_configured():
                logger.error("Discord not configured")
                return 1
            send_discord(html)
        mark_sent(td)
        ping_success()
    except Exception:
        logger.exception("Delivery failed")
        ping_failure("Delivery failed")
        return 1

    print(html)
    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "run":
        code = cmd_run(args)
        sys.exit(code)
    sys.exit(1)


if __name__ == "__main__":
    main()
