#!/usr/bin/env python3
"""Regenerate web/brief.html and web/snapshot.json from market_brief test fixtures."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
MB = REPO / "market_brief"
FIXTURES = MB / "tests" / "fixtures"

sys.path.insert(0, str(MB / "src"))

from brief.pipeline import build_brief  # noqa: E402
from brief.render import render_orbis_html  # noqa: E402


def _load(name: str) -> dict:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    for _key, val in list(data.items()):
        if isinstance(val, dict) and "as_of" in val and isinstance(val["as_of"], str):
            val["as_of"] = datetime.fromisoformat(val["as_of"])
    return data


def _load_gex() -> dict:
    data = json.loads((FIXTURES / "gex.json").read_text(encoding="utf-8"))
    data["as_of"] = datetime.fromisoformat(data["as_of"])
    for sym in data.get("symbols", {}).values():
        if isinstance(sym.get("as_of"), str):
            sym["as_of"] = datetime.fromisoformat(sym["as_of"])
        for _key, val in list(sym.items()):
            if isinstance(val, dict) and isinstance(val.get("as_of"), str):
                val["as_of"] = datetime.fromisoformat(val["as_of"])
    return data


def main() -> None:
    when = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)
    inject = {
        "markets": _load("markets.json"),
        "fred": _load("fred.json"),
        "sectors": _load("sectors.json"),
        "gex": _load_gex(),
        "calendar": {
            "events": [],
            "stale_after_minutes": 360,
            "source": "events.yaml",
            "as_of": datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
        },
    }
    payload, _ = build_brief(
        use_llm=False,
        thresholds_path=MB / "config" / "thresholds.yaml",
        events_path=MB / "config" / "events.yaml",
        inject=inject,
        when=when,
    )
    html = render_orbis_html(payload)
    meta = {
        "mode": "sample",
        "label": "SAMPLE — fixture data (2026-10-16 dry-run)",
        "source": "market_brief/tests/fixtures",
    }
    WEB.mkdir(exist_ok=True)
    (WEB / "brief.html").write_text(html, encoding="utf-8")
    (WEB / "snapshot.json").write_text(
        json.dumps({"meta": meta, "payload": payload.model_dump(mode="json")}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {WEB / 'brief.html'} ({len(html)} bytes)")


if __name__ == "__main__":
    main()