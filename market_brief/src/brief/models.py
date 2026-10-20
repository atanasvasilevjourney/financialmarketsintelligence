from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DataStatus(StrEnum):
    OK = "OK"
    STALE = "STALE"
    MISSING = "MISSING"


class DataPoint(BaseModel):
    """Single measured value with provenance and freshness."""

    value: float | None = None
    as_of: datetime | None = None
    source: str
    stale_after_minutes: int
    status: DataStatus = DataStatus.MISSING
    label: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def effective_status(self, now: datetime) -> DataStatus:
        if self.status == DataStatus.MISSING or self.value is None:
            return DataStatus.MISSING
        if self.as_of is None:
            return DataStatus.STALE
        age_min = (now - self.as_of).total_seconds() / 60.0
        if age_min > self.stale_after_minutes:
            return DataStatus.STALE
        return DataStatus.OK


class RegimeLabel(StrEnum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    CAUTION = "CAUTION"
    RISK_OFF = "RISK_OFF"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RegimeResult(BaseModel):
    label: RegimeLabel
    score_sum: int
    exposure_ceiling_pct: int
    reasons: list[str]
    inputs_used: list[str]
    inputs_missing: list[str]
    signal_scores: dict[str, int] = Field(default_factory=dict)


class MarketSnapshot(BaseModel):
    trading_date: str
    collected_at: datetime
    vix: DataPoint
    vix3m: DataPoint
    vix_term_ratio: DataPoint
    hy_oas: DataPoint
    hy_oas_zscore_252d: DataPoint
    yield_curve_10y2y: DataPoint
    spx: DataPoint
    spx_vs_50dma_pct: DataPoint
    spx_vs_200dma_pct: DataPoint
    sector_breadth: DataPoint
    rsp_spy_20d_rel_pct: DataPoint
    sector_details: dict[str, DataPoint] = Field(default_factory=dict)


GEX_DISPLAY_MAP: dict[str, str] = {"SPY": "SPX", "QQQ": "NDX"}


class GexSymbolBlock(BaseModel):
    """GEX levels from ORBIS sidecar (upstream ETF → index label for UI)."""

    upstream_symbol: str
    display_symbol: str
    spot: DataPoint
    net_gex: DataPoint
    gamma_regime: DataPoint
    call_wall: DataPoint
    put_wall: DataPoint
    zero_gamma: DataPoint
    max_pain: DataPoint | None = None


class ExposureFooter(BaseModel):
    exposure_pct: int
    bias: str
    regime_label: str
    new_entries: str
    reasoning: list[str] = Field(default_factory=list)


class EsTechnicals(BaseModel):
    """ES daily technicals — Phase 2 scaffold allows all MISSING until collector lands."""

    vs_20dma_pct: DataPoint
    vs_50dma_pct: DataPoint
    vs_200dma_pct: DataPoint
    rsi: DataPoint
    macd_state: DataPoint
    atr: DataPoint
    bollinger_position: DataPoint


class KpiStrip(BaseModel):
    es: DataPoint
    nq: DataPoint
    vix: DataPoint
    put_call: DataPoint


class CalendarEvent(BaseModel):
    title: str
    start_utc: datetime
    importance: str = "medium"
    source: str = "events.yaml"


class OpexBadge(BaseModel):
    """Monthly index OpEx proximity badge (third-Friday heuristic)."""

    monthly_opex_date: str
    badge: str = ""
    session_offset: int | None = None
    show_opex_block: bool = False
    rule: str = "spx_monthly_third_friday_nyse_weekdays"


class OpexFlowStub(BaseModel):
    """Placeholder until ORBIS sidecar v2 greek surface is wired."""

    status: DataStatus = DataStatus.MISSING
    note: str = "Sidecar v2 shadow γ / λG / charm not wired — net GEX only"
    lambda_g: DataPoint | None = None
    charm: DataPoint | None = None


class DeskContextEntry(BaseModel):
    source_id: str
    title: str
    url: str
    cadence: str
    themes: list[str] = Field(default_factory=list)
    alignment: str | None = None
    tension: str | None = None
    our_edge: str | None = None


class NarrativeBlock(BaseModel):
    headline: str
    bullets: list[str]
    tone: str = "neutral"
    lang: str = "bg"


class BriefPayload(BaseModel):
    trading_date: str
    generated_at: datetime
    regime: RegimeResult
    snapshot: MarketSnapshot
    calendar: list[CalendarEvent]
    narrative: NarrativeBlock
    degraded: bool = False
    collector_errors: list[str] = Field(default_factory=list)
    gex_symbols: list[GexSymbolBlock] = Field(default_factory=list)
    exposure_footer: ExposureFooter | None = None
    technicals_es: EsTechnicals | None = None
    kpi_strip: KpiStrip | None = None
    opex_badge: OpexBadge | None = None
    opex_flow: OpexFlowStub | None = None
    desk_context: list[DeskContextEntry] = Field(default_factory=list)
    alignment_summary: str | None = None


class NarrativeJSON(BaseModel):
    """Strict JSON shape expected from LLM."""

    headline: str
    bullets: list[str]
    tone: str = "neutral"
