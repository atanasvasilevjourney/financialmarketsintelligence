from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from brief.collectors.base import BaseCollector, CollectorError

TICKERS = {
    "vix": "^VIX",
    "vix3m": "^VIX3M",
    "spx": "^GSPC",
}


def _last_close(ticker: str) -> tuple[float, datetime]:
    hist = yf.Ticker(ticker).history(period="400d", interval="1d")
    if hist.empty:
        raise CollectorError(f"No history for {ticker}")
    row = hist.iloc[-1]
    ts = hist.index[-1]
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    as_of = ts.astimezone(UTC).to_pydatetime()
    return float(row["Close"]), as_of


def _dma_pct(ticker: str, window: int) -> tuple[float, datetime]:
    hist = yf.Ticker(ticker).history(period="400d", interval="1d")
    if len(hist) < window + 1:
        raise CollectorError(f"Insufficient history for {ticker} DMA{window}")
    closes = hist["Close"]
    dma = closes.rolling(window).mean().iloc[-1]
    last = closes.iloc[-1]
    ts = hist.index[-1]
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    as_of = ts.astimezone(UTC).to_pydatetime()
    pct = (float(last) / float(dma) - 1.0) * 100.0
    return pct, as_of


class MarketsCollector(BaseCollector):
    name = "markets"

    def __init__(self, stale_after_minutes: int = 120, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stale_after_minutes = stale_after_minutes

    def collect(self) -> dict[str, Any]:
        vix, vix_as_of = _last_close(TICKERS["vix"])
        vix3m, vix3m_as_of = _last_close(TICKERS["vix3m"])
        spx, spx_as_of = _last_close(TICKERS["spx"])
        vs50, vs50_as_of = _dma_pct(TICKERS["spx"], 50)
        vs200, vs200_as_of = _dma_pct(TICKERS["spx"], 200)
        ratio = vix / vix3m if vix3m else None
        ratio_as_of = max(vix_as_of, vix3m_as_of)
        return {
            "vix": {"value": vix, "as_of": vix_as_of},
            "vix3m": {"value": vix3m, "as_of": vix3m_as_of},
            "vix_term_ratio": {"value": ratio, "as_of": ratio_as_of},
            "spx": {"value": spx, "as_of": spx_as_of},
            "spx_vs_50dma_pct": {"value": vs50, "as_of": vs50_as_of},
            "spx_vs_200dma_pct": {"value": vs200, "as_of": vs200_as_of},
            "stale_after_minutes": self.stale_after_minutes,
            "source": "yfinance",
        }
