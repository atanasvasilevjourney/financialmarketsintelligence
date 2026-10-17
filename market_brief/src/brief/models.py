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


class CalendarEvent(BaseModel):
    title: str
    start_utc: datetime
    importance: str = "medium"
    source: str = "events.yaml"


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


class NarrativeJSON(BaseModel):
    """Strict JSON shape expected from LLM."""

    headline: str
    bullets: list[str]
    tone: str = "neutral"
