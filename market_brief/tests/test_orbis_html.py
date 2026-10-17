from __future__ import annotations

from pathlib import Path

from brief.pipeline import build_brief
from brief.render import render_orbis_html

ROOT = Path(__file__).resolve().parents[1]


def test_orbis_html_smoke(fixture_inject: dict, fixed_now) -> None:  # type: ignore[no-untyped-def]
    payload, _ = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        events_path=ROOT / "config" / "events.yaml",
        inject=fixture_inject,
        when=fixed_now,
    )
    html = render_orbis_html(payload)
    assert "ORBIS GEX — Daily Brief" in html
    assert "PRE-MARKET BRIEF" in html
    assert "GEX · OPTIONS GREEKS" in html
    assert "SPX" in html
    assert "NDX" in html
    assert "+1.25B" in html or "1.25B" in html
    assert "580" in html
    assert "9999" not in html and "12345" not in html
