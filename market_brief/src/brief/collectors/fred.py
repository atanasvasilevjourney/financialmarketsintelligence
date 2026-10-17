from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, cast

import pandas as pd

from brief.collectors.base import BaseCollector, CollectorError

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
HY_OAS_SERIES = "BAMLH0A0HYM2"
YIELD_SPREAD_SERIES = "T10Y2Y"


class FredCollector(BaseCollector):
    name = "fred"

    def __init__(
        self,
        api_key: str | None = None,
        stale_after_minutes: int = 1440,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self.stale_after_minutes = stale_after_minutes

    def _fetch_series(self, series_id: str, limit: int = 300) -> pd.DataFrame:
        if not self.api_key:
            raise CollectorError("FRED_API_KEY not set")
        params: dict[str, str | int] = {
            "series_id": series_id,
            "api_key": str(self.api_key),
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = self.client.get(FRED_BASE, params=params)
        resp.raise_for_status()
        payload = resp.json()
        obs = payload.get("observations", [])
        rows: list[tuple[datetime, float]] = []
        for item in obs:
            raw = item.get("value")
            if raw in (None, ".", ""):
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            dt = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=UTC)
            rows.append((dt, val))
        if not rows:
            raise CollectorError(f"No observations for {series_id}")
        df = pd.DataFrame(rows, columns=["date", "value"]).sort_values("date")
        return df

    def collect(self) -> dict[str, Any]:
        hy = self._fetch_series(HY_OAS_SERIES)
        spread = self._fetch_series(YIELD_SPREAD_SERIES, limit=30)
        hy_latest = hy.iloc[-1]
        spread_latest = spread.iloc[-1]

        def _as_utc(ts: datetime | pd.Timestamp) -> datetime:
            if isinstance(ts, datetime):
                dt = ts
            else:
                dt = cast(datetime, ts.to_pydatetime())
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)

        hy_as_of = _as_utc(hy_latest["date"])
        spread_as_of = _as_utc(spread_latest["date"])
        window = hy.tail(252)
        if len(window) >= 20:
            mean = window["value"].mean()
            std = window["value"].std(ddof=0) or 1.0
            z = float((hy_latest["value"] - mean) / std)
        else:
            z = None
        return {
            "hy_oas": {
                "value": float(hy_latest["value"]),
                "as_of": hy_as_of,
            },
            "hy_oas_zscore_252d": {
                "value": z,
                "as_of": hy_as_of,
            },
            "yield_curve_10y2y": {
                "value": float(spread_latest["value"]),
                "as_of": spread_as_of,
            },
            "stale_after_minutes": self.stale_after_minutes,
            "source": "fred.stlouisfed.org",
        }
