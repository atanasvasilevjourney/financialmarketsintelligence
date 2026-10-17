from __future__ import annotations

from datetime import UTC, datetime

from brief.models import DataPoint, DataStatus, MarketSnapshot, RegimeLabel
from brief.regime import compute_regime


def _dp(value: float) -> DataPoint:
    return DataPoint(
        value=value,
        as_of=datetime(2026, 10, 16, tzinfo=UTC),
        source="test",
        stale_after_minutes=9999,
        status=DataStatus.OK,
    )


def test_regime_risk_on_sample() -> None:
    snap = MarketSnapshot(
        trading_date="2026-10-16",
        collected_at=datetime(2026, 10, 16, tzinfo=UTC),
        vix=_dp(14),
        vix3m=_dp(18),
        vix_term_ratio=_dp(0.9),
        hy_oas=_dp(3.0),
        hy_oas_zscore_252d=_dp(-0.2),
        yield_curve_10y2y=_dp(0.4),
        spx=_dp(5800),
        spx_vs_50dma_pct=_dp(3),
        spx_vs_200dma_pct=_dp(5),
        sector_breadth=_dp(0.7),
        rsp_spy_20d_rel_pct=_dp(1.0),
    )
    result = compute_regime(snap)
    assert result.label in (RegimeLabel.RISK_ON, RegimeLabel.NEUTRAL)
    assert result.exposure_ceiling_pct > 0


def test_regime_insufficient_when_many_missing() -> None:
    missing = DataPoint(source="x", stale_after_minutes=1, status=DataStatus.MISSING)
    snap = MarketSnapshot(
        trading_date="2026-10-16",
        collected_at=datetime(2026, 10, 16, tzinfo=UTC),
        vix=missing,
        vix3m=missing,
        vix_term_ratio=missing,
        hy_oas=missing,
        hy_oas_zscore_252d=missing,
        yield_curve_10y2y=missing,
        spx=missing,
        spx_vs_50dma_pct=missing,
        spx_vs_200dma_pct=missing,
        sector_breadth=missing,
        rsp_spy_20d_rel_pct=missing,
    )
    result = compute_regime(snap)
    assert result.label == RegimeLabel.INSUFFICIENT_DATA
    assert result.exposure_ceiling_pct == 0
