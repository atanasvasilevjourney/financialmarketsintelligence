from __future__ import annotations

import json
import os
from typing import Any

from brief.models import BriefPayload, NarrativeBlock, NarrativeJSON
from brief.validate import validate_narrative_against_payload


def template_narrative(payload: BriefPayload, lang: str) -> NarrativeBlock:
    r = payload.regime.label.value
    if lang == "bg":
        headline = f"Пазарен режим: {r}"
        bullets = [
            f"Експозиция (таван): {payload.regime.exposure_ceiling_pct}%",
            f"Сигнали: {payload.regime.score_sum} (използвани {len(payload.regime.inputs_used)})",
        ]
        if payload.regime.inputs_missing:
            bullets.append(f"Липсващи входове: {', '.join(payload.regime.inputs_missing)}")
        if payload.degraded:
            bullets.append("Частични данни — проверете STALE/MISSING полета.")
    else:
        headline = f"Market regime: {r}"
        bullets = [
            f"Exposure ceiling: {payload.regime.exposure_ceiling_pct}%",
            f"Signal sum: {payload.regime.score_sum} ({len(payload.regime.inputs_used)} inputs)",
        ]
        if payload.regime.inputs_missing:
            bullets.append(f"Missing inputs: {', '.join(payload.regime.inputs_missing)}")
        if payload.degraded:
            bullets.append("Degraded data — review STALE/MISSING fields.")
    return NarrativeBlock(headline=headline, bullets=bullets, tone="neutral", lang=lang)


def generate_narrative(
    payload: BriefPayload,
    *,
    use_llm: bool = True,
    lang: str | None = None,
    model: str | None = None,
) -> NarrativeBlock:
    lang = lang or os.environ.get("BRIEF_LANG", "bg")
    if not use_llm or not os.environ.get("ANTHROPIC_API_KEY"):
        return template_narrative(payload, lang)

    import anthropic

    client = anthropic.Anthropic()
    model_id = model or os.environ.get("BRIEF_MODEL", "claude-sonnet-4-20250514")
    system = (
        "You write market commentary ONLY from the provided JSON. "
        "Do not invent numbers. Respond with strict JSON: "
        '{"headline": string, "bullets": string[], "tone": string}'
    )
    user_content = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)

    def _call() -> NarrativeJSON:
        msg = client.messages.create(
            model=model_id,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        block = msg.content[0] if msg.content else None
        text = getattr(block, "text", "{}") if block else "{}"
        # strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data: dict[str, Any] = json.loads(text)
        return NarrativeJSON.model_validate(data)

    for attempt in range(2):
        try:
            parsed = _call()
            errs = validate_narrative_against_payload(parsed, payload)
            if errs and attempt == 0:
                continue
            if errs:
                break
            return NarrativeBlock(
                headline=parsed.headline,
                bullets=parsed.bullets,
                tone=parsed.tone,
                lang=lang,
            )
        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
            if attempt == 1:
                break
    return template_narrative(payload, lang)
