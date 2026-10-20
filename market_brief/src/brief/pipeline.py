from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from brief.collectors.calendar import CalendarCollector
from brief.collectors.fred import FredCollector
from brief.collectors.gex_orbis import GexOrbisCollector
from brief.collectors.markets import MarketsCollector
from brief.collectors.sectors import SectorsCollector
from brief.desk_context import enrich_desk_alignment, load_desk_sources
from brief.models import (
    GEX_DISPLAY_MAP,
    BriefPayload,
    CalendarEvent,
    DataPoint,
    DataStatus,
    EsTechnicals,
    ExposureFooter,
    GexSymbolBlock,
    KpiStrip,
    MarketSnapshot,
    NarrativeBlock,
    OpexFlowStub,
    RegimeLabel,
    RegimeResult,
)
from brief.narrative import alignment_summary_stub, generate_narrative
from brief.opex_calendar import opex_badge_for
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
    sector_details: dict[str, DataPoint] = {}
    if sectors and sectors.get("sector_details"):
        stale_sectors = int(stale_cfg.get("sectors", 120))
        src = str(sectors.get("source", "yfinance"))
        for sym, detail in sectors["sector_details"].items():
            if not isinstance(detail, dict):
                continue
            price = detail.get("price")
            as_of = detail.get("as_of")
            if isinstance(as_of, str):
                as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if not isinstance(as_of, datetime):
                as_of = None
            val = float(price) if isinstance(price, (int, float)) else None
            dp = DataPoint(
                label=str(sym),
                value=val,
                as_of=as_of,
                source=src,
                stale_after_minutes=stale_sectors,
                status=DataStatus.OK if val is not None else DataStatus.MISSING,
                meta={
                    "above_50dma": bool(detail.get("above_50dma")),
                    "session_change_pct": detail.get("session_change_pct"),
                },
            )
            dp.status = dp.effective_status(now)
            sector_details[str(sym)] = dp
    snap = snap.model_copy(update={"sector_details": sector_details})
    return snap, errors


def _missing_point(label: str, source: str, stale_minutes: int) -> DataPoint:
    return DataPoint(
        label=label,
        source=source,
        stale_after_minutes=stale_minutes,
        status=DataStatus.MISSING,
    )


def _gex_field_point(
    sym_data: dict[str, Any],
    field: str,
    label: str,
    stale_minutes: int,
    now: datetime,
    *,
    force_stale: bool = False,
) -> DataPoint:
    raw = sym_data.get(field)
    source = str(sym_data.get("source", "orbis_sidecar"))
    if raw is None:
        return _missing_point(label, source, stale_minutes)
    if isinstance(raw, dict):
        inner: dict[str, object] = {
            "value": raw.get("value"),
            "as_of": raw.get("as_of"),
            "source": raw.get("source", source),
        }
        if raw.get("label") is not None:
            dp = point_from_raw(label, inner, source, stale_minutes, now)
            dp.label = str(raw.get("label"))
            if dp.value is None and dp.label:
                dp.status = DataStatus.OK if not force_stale else DataStatus.STALE
            if force_stale and dp.status == DataStatus.OK:
                dp.status = DataStatus.STALE
            return dp
        dp = point_from_raw(label, inner, source, stale_minutes, now)
    else:
        dp = point_from_raw(
            label,
            {"value": raw, "as_of": sym_data.get("as_of"), "source": source},
            source,
            stale_minutes,
            now,
        )
    if force_stale and dp.status == DataStatus.OK:
        dp.status = DataStatus.STALE
    return dp


def _build_gex_symbols(
    gex: dict[str, Any] | None,
    *,
    now: datetime,
    stale_minutes: int,
) -> list[GexSymbolBlock]:
    if not gex or not gex.get("symbols"):
        return []
    blocks: list[GexSymbolBlock] = []
    symbols: dict[str, Any] = gex["symbols"]
    for upstream, display in GEX_DISPLAY_MAP.items():
        sym_data = symbols.get(upstream)
        if not sym_data:
            continue
        force_stale = bool(sym_data.get("stale"))
        blocks.append(
            GexSymbolBlock(
                upstream_symbol=upstream,
                display_symbol=display,
                spot=_gex_field_point(sym_data, "spot", f"{display} spot", stale_minutes, now, force_stale=force_stale),
                net_gex=_gex_field_point(sym_data, "net", f"{display} net GEX", stale_minutes, now, force_stale=force_stale),
                gamma_regime=_gex_field_point(
                    sym_data, "regime", f"{display} gamma", stale_minutes, now, force_stale=force_stale
                ),
                call_wall=_gex_field_point(
                    sym_data, "callWall", f"{display} call wall", stale_minutes, now, force_stale=force_stale
                ),
                put_wall=_gex_field_point(
                    sym_data, "putWall", f"{display} put wall", stale_minutes, now, force_stale=force_stale
                ),
                zero_gamma=_gex_field_point(
                    sym_data, "flip", f"{display} zero gamma", stale_minutes, now, force_stale=force_stale
                ),
                max_pain=_gex_field_point(
                    sym_data, "maxPain", f"{display} max pain", stale_minutes, now, force_stale=force_stale
                ),
            )
        )
    return blocks


def _build_exposure_footer(regime: RegimeResult) -> ExposureFooter:
    bias_map = {
        RegimeLabel.RISK_ON: "RISK-ON",
        RegimeLabel.NEUTRAL: "NEUTRAL",
        RegimeLabel.CAUTION: "CAUTION",
        RegimeLabel.RISK_OFF: "RISK-OFF",
        RegimeLabel.INSUFFICIENT_DATA: "STAND DOWN",
    }
    entries_map = {
        RegimeLabel.RISK_ON: "ALLOW",
        RegimeLabel.NEUTRAL: "SELECTIVE",
        RegimeLabel.CAUTION: "LIMITED",
        RegimeLabel.RISK_OFF: "NONE",
        RegimeLabel.INSUFFICIENT_DATA: "NONE",
    }
    return ExposureFooter(
        exposure_pct=regime.exposure_ceiling_pct,
        bias=bias_map.get(regime.label, regime.label.value),
        regime_label=regime.label.value,
        new_entries=entries_map.get(regime.label, "NONE"),
        reasoning=regime.reasons[:5],
    )


def _build_technicals_placeholder(stale_minutes: int) -> EsTechnicals:
    src = "technicals_todo"
    return EsTechnicals(
        vs_20dma_pct=_missing_point("vs_20dma_pct", src, stale_minutes),
        vs_50dma_pct=_missing_point("vs_50dma_pct", src, stale_minutes),
        vs_200dma_pct=_missing_point("vs_200dma_pct", src, stale_minutes),
        rsi=_missing_point("rsi", src, stale_minutes),
        macd_state=_missing_point("macd_state", src, stale_minutes),
        atr=_missing_point("atr", src, stale_minutes),
        bollinger_position=_missing_point("bollinger_position", src, stale_minutes),
    )


def _build_kpi_strip(
    snapshot: MarketSnapshot,
    markets: dict[str, Any] | None,
    *,
    now: datetime,
    stale_minutes: int,
) -> KpiStrip:
    todo = "equity_pc_todo"
    es = _point("es_future", markets, "es_future", stale_minutes, now)
    nq = _point("nq_future", markets, "nq_future", stale_minutes, now)
    if es.status == DataStatus.MISSING:
        es = _missing_point("ES futures", "yfinance", stale_minutes)
    else:
        es.label = "ES"
    if nq.status == DataStatus.MISSING:
        nq = _missing_point("NQ futures", "yfinance", stale_minutes)
    else:
        nq.label = "NQ"
    return KpiStrip(
        es=es,
        nq=nq,
        vix=snapshot.vix,
        put_call=_missing_point("Equity P/C", todo, stale_minutes),
    )


def _build_opex_flow_stub(*, show_block: bool) -> OpexFlowStub:
    if not show_block:
        return OpexFlowStub(
            status=DataStatus.MISSING,
            note="OpEx block inactive (outside T-1/T0/T+1 window)",
        )
    return OpexFlowStub(
        status=DataStatus.MISSING,
        note="Sidecar v2 shadow γ / λG / charm not wired — net GEX only",
    )


def run_collectors(
    *,
    http_client: Any = None,
    thresholds_path: Path | None = None,
    events_path: Path | None = None,
    inject: dict[str, dict[str, Any]] | None = None,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[str],
]:
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
    gex = _run(
        "gex",
        lambda: GexOrbisCollector(
            stale_after_minutes=int(stale.get("gex_orbis", 60)),
            client=http_client,
        ),
    )
    return markets, fred, sectors, calendar, gex, errors


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
    markets, fred, sectors, calendar, gex, errors = run_collectors(
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
    td_date = datetime.fromisoformat(td).date()
    opex_badge = opex_badge_for(td_date)
    gex_stale = int(stale_cfg.get("gex_orbis", 60))
    if gex is None:
        all_errors = all_errors + ["gex: collector failed"]
    gex_symbols = _build_gex_symbols(gex, now=now, stale_minutes=gex_stale)
    exposure_footer = _build_exposure_footer(regime)
    technicals_es = _build_technicals_placeholder(int(stale_cfg.get("technicals", 120)))
    market_stale = int(stale_cfg.get("markets", 120))
    kpi_strip = _build_kpi_strip(snapshot, markets, now=now, stale_minutes=market_stale)
    desk_raw = load_desk_sources()
    opex_flow = _build_opex_flow_stub(show_block=opex_badge.show_opex_block)
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
        gex_symbols=gex_symbols,
        exposure_footer=exposure_footer,
        technicals_es=technicals_es,
        kpi_strip=kpi_strip,
        opex_badge=opex_badge,
        opex_flow=opex_flow,
        desk_context=desk_raw,
    )
    payload = payload.model_copy(
        update={"desk_context": enrich_desk_alignment(payload.desk_context, payload)}
    )
    payload = payload.model_copy(
        update={
            "alignment_summary": alignment_summary_stub(payload),
            "narrative": generate_narrative(payload, use_llm=use_llm),
        }
    )
    html = render_html(payload)
    return payload, html


def is_total_failure(payload: BriefPayload) -> bool:
    return payload.regime.label == RegimeLabel.INSUFFICIENT_DATA and len(payload.regime.inputs_used) == 0
