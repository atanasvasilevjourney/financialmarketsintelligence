from __future__ import annotations

from datetime import datetime

from brief.models import BriefPayload, DataPoint, DataStatus, NarrativeJSON


def point_from_raw(
    label: str,
    raw: dict[str, object] | None,
    source: str,
    stale_after_minutes: int,
    now: datetime,
) -> DataPoint:
    if raw is None:
        return DataPoint(
            label=label,
            source=source,
            stale_after_minutes=stale_after_minutes,
            status=DataStatus.MISSING,
        )
    value_raw = raw.get("value")
    as_of = raw.get("as_of")
    if not isinstance(as_of, datetime):
        as_of = None
    value: float | None
    if value_raw is None:
        value = None
    elif isinstance(value_raw, (int, float)):
        value = float(value_raw)
    else:
        value = None
    dp = DataPoint(
        label=label,
        value=value,
        as_of=as_of,
        source=str(raw.get("source", source)),
        stale_after_minutes=stale_after_minutes,
        status=DataStatus.OK if value is not None else DataStatus.MISSING,
    )
    eff = dp.effective_status(now)
    dp.status = eff
    return dp


def validate_narrative_against_payload(
    narrative: NarrativeJSON, payload: BriefPayload
) -> list[str]:
    """Ensure LLM did not invent numeric facts in bullets (basic guard)."""
    errors: list[str] = []
    forbidden_tokens: list[str] = []
    snap = payload.snapshot
    for field_name in (
        "vix",
        "hy_oas",
        "yield_curve_10y2y",
        "spx",
        "sector_breadth",
    ):
        dp: DataPoint = getattr(snap, field_name)
        if dp.value is not None and dp.status == DataStatus.OK:
            forbidden_tokens.append(f"{dp.value:.2f}")
    text = narrative.headline + " " + " ".join(narrative.bullets)
    for token in forbidden_tokens:
        if token in text:
            errors.append(f"Narrative repeats computed number {token}")
    if not narrative.headline.strip():
        errors.append("Empty headline")
    if not narrative.bullets:
        errors.append("No bullets")
    return errors
