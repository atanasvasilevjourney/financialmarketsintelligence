from __future__ import annotations

from datetime import datetime
from pathlib import Path

from brief.models import DataStatus, RegimeLabel
from brief.pipeline import build_brief, is_total_failure

ROOT = Path(__file__).resolve().parents[1]


def test_offline_dry_brief(fixture_inject: dict, fixed_now: datetime) -> None:  # type: ignore[name-defined]
    payload, html = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        events_path=ROOT / "config" / "events.yaml",
        inject=fixture_inject,
        when=fixed_now,
    )
    assert payload.regime.label != RegimeLabel.INSUFFICIENT_DATA
    assert "Market Brief" in html
    assert payload.snapshot.vix.status == DataStatus.OK
    assert not is_total_failure(payload)


def test_degraded_when_fred_missing(fixture_inject: dict, fixed_now: datetime) -> None:  # type: ignore[name-defined]
    inject = dict(fixture_inject)
    inject["fred"] = None  # simulate collector failure without network
    payload, html = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        inject=inject,
        when=fixed_now,
    )
    assert payload.degraded
    assert payload.snapshot.hy_oas.status == DataStatus.MISSING
    assert "n/a" in html or "MISSING" in html
    assert any("fred" in e for e in payload.collector_errors)
    # Brief still completes with markets + sectors
    assert payload.snapshot.vix.status == DataStatus.OK
    assert payload.regime.label != RegimeLabel.INSUFFICIENT_DATA


def test_stale_datapoint(fixed_now: datetime) -> None:
    from datetime import timedelta

    from brief.validate import point_from_raw

    old = fixed_now - timedelta(days=3)
    dp = point_from_raw(
        "vix",
        {"value": 20.0, "as_of": old, "source": "test"},
        "test",
        120,
        fixed_now,
    )
    assert dp.status == DataStatus.STALE
