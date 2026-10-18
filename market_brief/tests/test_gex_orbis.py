from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx

from brief.collectors.gex_orbis import GexOrbisCollector, normalize_daily_payload
from brief.models import DataStatus
from brief.pipeline import build_brief

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_daily_payload_camel_case() -> None:
    body = {
        "spot": 100.0,
        "netGex": 1e9,
        "zeroGamma": 99.0,
        "callWall": 105.0,
        "putWall": 95.0,
        "regime": "transitional",
        "source": "cache",
        "asOf": "2026-10-16T12:00:00+00:00",
    }
    out = normalize_daily_payload(body, "SPY")
    assert out["spot"]["value"] == 100.0
    assert out["net"]["value"] == 1e9
    assert out["regime"]["label"] == "transitional"


def test_gex_collector_from_fixture_responses() -> None:
    spy_body = json.loads((FIXTURES / "sidecar_spy.json").read_text(encoding="utf-8"))
    qqq_body = json.loads((FIXTURES / "sidecar_qqq.json").read_text(encoding="utf-8"))

    health_hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/health"):
            health_hits.append("health")
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/daily/SPY/latest"):
            return httpx.Response(200, json=spy_body)
        if request.url.path.endswith("/daily/QQQ/latest"):
            return httpx.Response(200, json=qqq_body)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://orbis-gex.onrender.com")
    with GexOrbisCollector(client=client) as col:
        data = col.collect()
    assert health_hits == ["health"]
    assert "SPY" in data["symbols"]
    assert data["symbols"]["SPY"]["net"]["value"] == 1250000000.0


def test_degraded_when_gex_sidecar_down(fixture_inject: dict, fixed_now: datetime) -> None:  # type: ignore[name-defined]
    inject = dict(fixture_inject)
    inject["gex"] = None
    payload, _html = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        events_path=ROOT / "config" / "events.yaml",
        inject=inject,
        when=fixed_now,
    )
    assert payload.degraded
    assert not payload.gex_symbols
    assert any("gex" in e for e in payload.collector_errors)


def test_gex_wired_in_payload(fixture_inject: dict, fixed_now: datetime) -> None:  # type: ignore[name-defined]
    payload, _ = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        events_path=ROOT / "config" / "events.yaml",
        inject=fixture_inject,
        when=fixed_now,
    )
    assert len(payload.gex_symbols) == 2
    spx = next(g for g in payload.gex_symbols if g.display_symbol == "SPX")
    assert spx.net_gex.value == 1250000000.0
    assert spx.net_gex.status == DataStatus.OK
    ndx = next(g for g in payload.gex_symbols if g.display_symbol == "NDX")
    assert ndx.net_gex.status == DataStatus.STALE
