from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from brief.collectors.base import BaseCollector, CollectorError

DEFAULT_SIDECAR_URL = "https://orbis-gex.onrender.com"
UPSTREAM_SYMBOLS = ("SPY", "QQQ")


def sidecar_base_url() -> str:
    return os.environ.get("ORBIS_SIDECAR_URL", DEFAULT_SIDECAR_URL).rstrip("/")


def _parse_as_of(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def normalize_daily_payload(body: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Map sidecar JSON (camelCase) into collector field dict."""
    as_of = _parse_as_of(body.get("as_of") or body.get("asOf") or body.get("trade_date"))
    stale = bool(body.get("stale") or body.get("is_stale"))
    source = str(body.get("source") or "orbis_sidecar")
    fields = {
        "spot": body.get("spot"),
        "net": body.get("net") or body.get("netGex") or body.get("net_gex"),
        "flip": body.get("flip") or body.get("zeroGamma") or body.get("zero_gamma"),
        "callWall": body.get("callWall") or body.get("call_wall"),
        "putWall": body.get("putWall") or body.get("put_wall"),
        "maxPain": body.get("maxPain") or body.get("max_pain"),
        "regime": body.get("regime") or body.get("gamma_regime"),
    }
    out: dict[str, Any] = {"symbol": symbol, "source": source, "stale": stale, "as_of": as_of}
    for key, val in fields.items():
        if val is None:
            continue
        if key == "regime":
            out[key] = {"value": None, "label": str(val), "as_of": as_of, "source": source}
        elif isinstance(val, (int, float)):
            out[key] = {"value": float(val), "as_of": as_of, "source": source}
        else:
            out[key] = {"value": None, "label": str(val), "as_of": as_of, "source": source}
    return out


class GexOrbisCollector(BaseCollector):
    name = "gex_orbis"

    def __init__(self, stale_after_minutes: int = 60, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stale_after_minutes = stale_after_minutes

    def collect(self) -> dict[str, Any]:
        base = sidecar_base_url()
        symbols: dict[str, dict[str, Any]] = {}
        latest_as_of: datetime | None = None
        for sym in UPSTREAM_SYMBOLS:
            url = f"{base}/daily/{sym}/latest"
            resp = self.client.get(url)
            if resp.status_code >= 400:
                raise CollectorError(f"{sym}: HTTP {resp.status_code} from {url}")
            body = resp.json()
            if not isinstance(body, dict):
                raise CollectorError(f"{sym}: expected JSON object")
            normalized = normalize_daily_payload(body, sym)
            symbols[sym] = normalized
            ao = normalized.get("as_of")
            if isinstance(ao, datetime):
                latest_as_of = ao if latest_as_of is None else max(latest_as_of, ao)
        return {
            "symbols": symbols,
            "as_of": latest_as_of,
            "stale_after_minutes": self.stale_after_minutes,
            "source": "orbis_sidecar",
        }
