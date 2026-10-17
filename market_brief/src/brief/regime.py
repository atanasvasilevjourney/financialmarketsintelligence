from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from brief.models import DataPoint, DataStatus, MarketSnapshot, RegimeLabel, RegimeResult

DEFAULT_THRESHOLDS = Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_THRESHOLDS
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _score_three_band(value: float, risk_on: float, neutral: float, caution: float, higher_is_worse: bool) -> int:
    if higher_is_worse:
        if value <= risk_on:
            return 1
        if value <= neutral:
            return 0
        if value <= caution:
            return -1
        return -1
    # higher is better
    if value >= risk_on:
        return 1
    if value >= neutral:
        return 0
    if value >= caution:
        return -1
    return -1


def _score_point(name: str, dp: DataPoint, cfg: dict[str, Any]) -> tuple[int | None, str | None]:
    if dp.status != DataStatus.OK or dp.value is None:
        return None, None
    v = dp.value
    signals = cfg.get("signals", {})
    if name == "vix":
        s = signals["vix"]
        sc = _score_three_band(v, s["risk_on_max"], s["neutral_max"], s["caution_max"], True)
        return sc, f"VIX {v:.1f}"
    if name == "vix_term_ratio":
        s = signals["vix_term_ratio"]
        sc = _score_three_band(v, s["risk_on_max"], s["neutral_max"], s["caution_max"], True)
        return sc, f"VIX/VIX3M {v:.2f}"
    if name == "hy_oas_zscore_252d":
        s = signals["hy_oas_zscore_252d"]
        sc = _score_three_band(v, s["risk_on_max"], s["neutral_max"], s["caution_max"], True)
        return sc, f"HY OAS z252 {v:.2f}"
    if name == "yield_curve_10y2y":
        s = signals["yield_curve_10y2y"]
        sc = _score_three_band(v, s["risk_on_min"], s["neutral_min"], s["caution_min"], False)
        return sc, f"10y-2y {v:.2f}%"
    if name == "spx_vs_50dma":
        s = signals["spx_vs_50dma"]
        sc = _score_three_band(v, s["risk_on_min"], s["neutral_min"], s["caution_min"], False)
        return sc, f"SPX vs 50DMA {v:+.1f}%"
    if name == "spx_vs_200dma":
        s = signals["spx_vs_200dma"]
        sc = _score_three_band(v, s["risk_on_min"], s["neutral_min"], s["caution_min"], False)
        return sc, f"SPX vs 200DMA {v:+.1f}%"
    if name == "sector_breadth":
        s = signals["sector_breadth"]
        sc = _score_three_band(v, s["risk_on_min"], s["neutral_min"], s["caution_min"], False)
        return sc, f"Sector breadth {v:.0%}"
    if name == "rsp_spy_20d":
        s = signals["rsp_spy_20d"]
        sc = _score_three_band(v, s["risk_on_min"], s["neutral_min"], s["caution_min"], False)
        return sc, f"RSP/SPY 20d {v:+.2f}%"
    return None, None


def compute_regime(snapshot: MarketSnapshot, cfg: dict[str, Any] | None = None) -> RegimeResult:
    thresholds = cfg or load_thresholds()
    inputs: list[tuple[str, DataPoint]] = [
        ("vix", snapshot.vix),
        ("vix_term_ratio", snapshot.vix_term_ratio),
        ("hy_oas_zscore_252d", snapshot.hy_oas_zscore_252d),
        ("yield_curve_10y2y", snapshot.yield_curve_10y2y),
        ("spx_vs_50dma", snapshot.spx_vs_50dma_pct),
        ("spx_vs_200dma", snapshot.spx_vs_200dma_pct),
        ("sector_breadth", snapshot.sector_breadth),
        ("rsp_spy_20d", snapshot.rsp_spy_20d_rel_pct),
    ]
    used: list[str] = []
    missing: list[str] = []
    scores: dict[str, int] = {}
    reasons: list[str] = []
    total = 0
    for key, dp in inputs:
        sc, reason = _score_point(key, dp, thresholds)
        if sc is None:
            missing.append(key)
            continue
        used.append(key)
        scores[key] = sc
        total += sc
        if reason:
            reasons.append(reason)
    max_missing = int(thresholds.get("max_missing_inputs", 2))
    ceilings = thresholds.get("exposure_ceiling_pct", {})
    if len(missing) > max_missing:
        return RegimeResult(
            label=RegimeLabel.INSUFFICIENT_DATA,
            score_sum=total,
            exposure_ceiling_pct=int(ceilings.get("INSUFFICIENT_DATA", 0)),
            reasons=reasons,
            inputs_used=used,
            inputs_missing=missing,
            signal_scores=scores,
        )
    bands = thresholds.get("sum_to_regime", {})
    if total >= int(bands.get("risk_on_min", 4)):
        label = RegimeLabel.RISK_ON
    elif total >= int(bands.get("neutral_min", 1)):
        label = RegimeLabel.NEUTRAL
    elif total >= int(bands.get("caution_min", -2)):
        label = RegimeLabel.CAUTION
    else:
        label = RegimeLabel.RISK_OFF
    return RegimeResult(
        label=label,
        score_sum=total,
        exposure_ceiling_pct=int(ceilings.get(label.value, 0)),
        reasons=reasons,
        inputs_used=used,
        inputs_missing=missing,
        signal_scores=scores,
    )
