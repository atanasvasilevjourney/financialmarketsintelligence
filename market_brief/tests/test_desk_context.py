from __future__ import annotations

from pathlib import Path

from brief.desk_context import enrich_desk_alignment, load_desk_sources
from brief.pipeline import build_brief

ROOT = Path(__file__).resolve().parents[1]


def test_load_desk_sources_schema() -> None:
    entries = load_desk_sources(ROOT / "config" / "desk_sources.yaml")
    assert len(entries) >= 2
    paralia = next(e for e in entries if e.source_id == "paralia")
    assert "inflation" in paralia.themes
    assert paralia.url.startswith("https://")


def test_desk_context_in_payload(fixture_inject: dict, fixed_now) -> None:  # type: ignore[no-untyped-def]
    payload, _ = build_brief(
        use_llm=False,
        thresholds_path=ROOT / "config" / "thresholds.yaml",
        events_path=ROOT / "config" / "events.yaml",
        inject=fixture_inject,
        when=fixed_now,
    )
    assert payload.desk_context
    assert payload.alignment_summary
    enriched = enrich_desk_alignment(payload.desk_context, payload)
    assert enriched[0].alignment in ("partial", "tension")
    assert enriched[0].our_edge
