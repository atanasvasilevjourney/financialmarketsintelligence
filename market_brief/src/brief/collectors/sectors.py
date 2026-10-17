from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from brief.collectors.base import BaseCollector, CollectorError

SECTOR_ETFS = [
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLU",
    "XLRE",
    "XLC",
]


def _above_50dma(symbol: str) -> tuple[bool, float | None, datetime | None]:
    hist = yf.Ticker(symbol).history(period="120d", interval="1d")
    if len(hist) < 55:
        return False, None, None
    closes = hist["Close"]
    dma50 = closes.rolling(50).mean().iloc[-1]
    last = closes.iloc[-1]
    ts = hist.index[-1]
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    as_of = ts.astimezone(UTC).to_pydatetime()
    return bool(last >= dma50), float(last), as_of


def _rsp_spy_20d_rel() -> tuple[float, datetime]:
    rsp = yf.Ticker("RSP").history(period="40d", interval="1d")["Close"]
    spy = yf.Ticker("SPY").history(period="40d", interval="1d")["Close"]
    if len(rsp) < 21 or len(spy) < 21:
        raise CollectorError("Insufficient RSP/SPY history")
    rsp_ret = float(rsp.iloc[-1] / rsp.iloc[-21] - 1.0)
    spy_ret = float(spy.iloc[-1] / spy.iloc[-21] - 1.0)
    rel_pct = (rsp_ret - spy_ret) * 100.0
    ts = spy.index[-1]
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    as_of = ts.astimezone(UTC).to_pydatetime()
    return rel_pct, as_of


class SectorsCollector(BaseCollector):
    name = "sectors"

    def __init__(self, stale_after_minutes: int = 120, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stale_after_minutes = stale_after_minutes

    def collect(self) -> dict[str, Any]:
        above = 0
        total = 0
        details: dict[str, dict[str, Any]] = {}
        latest_as_of: datetime | None = None
        for sym in SECTOR_ETFS:
            ok, price, as_of = _above_50dma(sym)
            if price is not None and as_of is not None:
                total += 1
                above += 1 if ok else 0
                details[sym] = {"above_50dma": ok, "price": price, "as_of": as_of}
                latest_as_of = as_of if latest_as_of is None else max(latest_as_of, as_of)
        if total == 0:
            raise CollectorError("No sector ETF data")
        breadth = above / total
        rel, rel_as_of = _rsp_spy_20d_rel()
        as_of = max(latest_as_of, rel_as_of) if latest_as_of else rel_as_of
        return {
            "sector_breadth": {"value": breadth, "as_of": as_of},
            "rsp_spy_20d_rel_pct": {"value": rel, "as_of": rel_as_of},
            "sector_details": details,
            "stale_after_minutes": self.stale_after_minutes,
            "source": "yfinance",
        }
