from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from brief.collectors.calendar import CalendarCollector
from brief.collectors.fred import FredCollector
from brief.collectors.markets import MarketsCollector
from brief.collectors.sectors import SectorsCollector
from brief.models import (
    BriefPayload,
    CalendarEvent,
    DataPoint,
    MarketSnapshot,
    NarrativeBlock,
    RegimeLabel,
)
from brief.narrative import generate_narrative
from brief.regime import compute_regime, load_thresholds
from brief.render import render_html
from brief.validate import point_from_raw

logger = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


def trading_date_now(when: datetime | None = None) -> str:
    dt = when or datetime.now(UTC)
    return dt.astimezone(NY).date().isoformat()


def in_nyse_send_window(when: datetime | None = None) -> bool:
    """True between 07:30 and 08:30 America/New_York (scheduler guard)."""
    dt = (when or datetime.now(UTC)).astimezone(NY)
    start = time(7, 30)
    end = time(8, 30)
    t = dt.time()
    return start <= t <= end


def _point(
    label: str,
    blob: dict[str, Any] | None,
    key: str,
    stale_minutes: int,
    now: datetime,
) -> DataPoint:
    raw: dict[str, object] | None = None
    if blob and key in blob and isinstance(blob[key], dict):
        inner = blob[key]
        raw = {
            "value": inner.get("value"),
            "as_of": inner.get("as_of"),
            "source": blob.get("source", label),
        }
    return point_from_raw(label, raw, str(blob.get("source", label)) if blob else label, stale_minutes, now)


def _build_snapshot(
    *,
    markets: dict[str, Any] | None,
    fred: dict[str, Any] | None,
    sectors: dict[str, Any] | None,
    trading_date: str,
    now: datetime,
    stale_cfg: dict[str, int],
) -> tuple[MarketSnapshot, list[str]]:
    errors: list[str] = []
    snap = MarketSnapshot(
        trading_date=trading_date,
        collected_at=now,
        vix=_point("vix", markets, "vix", int(stale_cfg.get("markets", 120)), now),
        vix3m=_point("vix3m", markets, "vix3m", int(stale_cfg.get("markets", 120)), now),
        vix_term_ratio=_point(
            "vix_term_ratio", markets, "vix_term_ratio", int(stale_cfg.get("markets", 120)), now
        ),
        hy_oas=_point("hy_oas", fred, "hy_oas", int(stale_cfg.get("fred", 1440)), now),
        hy_oas_zscore_252d=_point(
            "hy_oas_zscore_252d", fred, "hy_oas_zscore_252d", int(stale_cfg.get("fred", 1440)), now
        ),
        yield_curve_10y2y=_point(
            "yield_curve_10y2y", fred, "yield_curve_10y2y", int(stale_cfg.get("fred", 1440)), now
        ),
        spx=_point("spx", markets, "spx", int(stale_cfg.get("markets", 120)), now),
        spx_vs_50dma_pct=_point(
            "spx_vs_50dma", markets, "spx_vs_50dma_pct", int(stale_cfg.get("markets", 120)), now
        ),
        spx_vs_200dma_pct=_point(
            "spx_vs_200dma", markets, "spx_vs_200dma_pct", int(stale_cfg.get("markets", 120)), now
        ),
        sector_breadth=_point(
            "sector_breadth", sectors, "sector_breadth", int(stale_cfg.get("sectors", 120)), now
        ),
        rsp_spy_20d_rel_pct=_point(
            "rsp_spy_20d", sectors, "rsp_spy_20d_rel_pct", int(stale_cfg.get("sectors", 120)), now
        ),
    )
    if markets is None:
        errors.append("markets collector failed")
    if fred is None:
        errors.append("fred collector failed")
    if sectors is None:
        errors.append("sectors collector failed")
    return snap, errors


def run_collectors(
    *,
    http_client: Any = None,
    thresholds_path: Path | None = None,
    events_path: Path | None = None,
    inject: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Run all collectors; never raise — return Nones on failure."""
    cfg = load_thresholds(thresholds_path)
    stale = cfg.get("stale_after_minutes", {})
    errors: list[str] = []
    inject = inject or {}

    def _run(name: str, factory: Any) -> dict[str, Any] | None:
        if name in inject:
            val = inject[name]
            if val is None:
                errors.append(f"{name}: collector failed")
            return val
        try:
            with factory() as col:
                out: dict[str, Any] = col.collect()
                return out
        except Exception as exc:  # noqa: BLE001 — degrade brief per spec
            logger.exception("Collector %s failed", name)
            errors.append(f"{name}: {exc}")
            return None

    markets = _run(
        "markets",
        lambda: MarketsCollector(stale_after_minutes=int(stale.get("markets", 120)), client=http_client),
    )
    fred = _run(
        "fred",
        lambda: FredCollector(stale_after_minutes=int(stale.get("fred", 1440)), client=http_client),
    )
    sectors = _run(
        "sectors",
        lambda: SectorsCollector(stale_after_minutes=int(stale.get("sectors", 120)), client=http_client),
    )
    calendar = _run(
        "calendar",
        lambda: CalendarCollector(
            events_path=events_path,
            stale_after_minutes=int(stale.get("calendar", 360)),
            client=http_client,
        ),
    )
    return markets, fred, sectors, calendar, errors


def build_brief(
    *,
    use_llm: bool = True,
    thresholds_path: Path | None = None,
    events_path: Path | None = None,
    inject: dict[str, dict[str, Any]] | None = None,
    when: datetime | None = None,
) -> tuple[BriefPayload, str]:
    now = when or datetime.now(UTC)
    td = trading_date_now(now)
    cfg = load_thresholds(thresholds_path)
    stale_cfg = cfg.get("stale_after_minutes", {})
    markets, fred, sectors, calendar, errors = run_collectors(
        thresholds_path=thresholds_path,
        events_path=events_path,
        inject=inject,
    )
    snapshot, snap_errors = _build_snapshot(
        markets=markets,
        fred=fred,
        sectors=sectors,
        trading_date=td,
        now=now,
        stale_cfg=stale_cfg,
    )
    all_errors = errors + snap_errors
    regime = compute_regime(snapshot, cfg)
    events: list[CalendarEvent] = []
    if calendar and calendar.get("events"):
        for ev in calendar["events"]:
            events.append(CalendarEvent.model_validate(ev))
    degraded = bool(all_errors) or len(regime.inputs_missing) > 0
    payload = BriefPayload(
        trading_date=td,
        generated_at=now,
        regime=regime,
        snapshot=snapshot,
        calendar=events,
        narrative=NarrativeBlock(headline="", bullets=[], lang="bg"),
        degraded=degraded,
        collector_errors=all_errors,
    )
    payload = payload.model_copy(
        update={"narrative": generate_narrative(payload, use_llm=use_llm)}
    )
    html = render_html(payload)
    return payload, html


def is_total_failure(payload: BriefPayload) -> bool:
    return payload.regime.label == RegimeLabel.INSUFFICIENT_DATA and len(payload.regime.inputs_used) == 0
