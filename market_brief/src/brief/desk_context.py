from __future__ import annotations

from pathlib import Path

import yaml

from brief.models import BriefPayload, DeskContextEntry, RegimeLabel

DEFAULT_DESK_SOURCES_PATH = Path(__file__).resolve().parents[2] / "config" / "desk_sources.yaml"


def load_desk_sources(path: Path | None = None) -> list[DeskContextEntry]:
    """Load curated desk sources (themes + URLs only — no scraped numbers)."""
    p = path or DEFAULT_DESK_SOURCES_PATH
    if not p.is_file():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or []
    out: list[DeskContextEntry] = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id", "unknown"))
        out.append(
            DeskContextEntry(
                source_id=sid,
                title=str(item.get("title", sid)),
                url=str(item.get("url", "")),
                cadence=str(item.get("cadence", "unknown")),
                themes=[str(t) for t in (item.get("themes") or [])],
            )
        )
    return out


def enrich_desk_alignment(entries: list[DeskContextEntry], payload: BriefPayload) -> list[DeskContextEntry]:
    """Deterministic alignment stub (no LLM, no external scrape)."""
    regime = payload.regime.label
    gex_ok = any(g.net_gex.status.value == "OK" for g in payload.gex_symbols)
    enriched: list[DeskContextEntry] = []
    for e in entries:
        alignment = "partial"
        if regime in (RegimeLabel.RISK_ON, RegimeLabel.NEUTRAL):
            alignment = "partial"
        elif regime in (RegimeLabel.CAUTION, RegimeLabel.RISK_OFF):
            alignment = "tension"
        tension = (
            f"Desk themes {', '.join(e.themes) or 'n/a'}; "
            f"our regime {regime.value} ({payload.regime.exposure_ceiling_pct}% ceiling)"
        )
        if payload.degraded:
            tension += "; payload degraded — verify STALE/MISSING before comparing narratives"
        our_edge = "ORBIS net GEX + regime engine" if gex_ok else "Regime engine (GEX MISSING this run)"
        enriched.append(
            e.model_copy(
                update={
                    "alignment": alignment,
                    "tension": tension,
                    "our_edge": our_edge,
                }
            )
        )
    return enriched
