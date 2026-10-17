from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from brief.models import BriefPayload, DataPoint, DataStatus

SOFIA = ZoneInfo("Europe/Sofia")
NY = ZoneInfo("America/New_York")


def _fmt_value(dp: DataPoint, *, as_pct: bool = False) -> str:
    if dp.status == DataStatus.MISSING or dp.value is None:
        return "n/a"
    if dp.status == DataStatus.STALE:
        if as_pct:
            return f"STALE ({dp.value:.0%})"
        return f"STALE ({dp.value:.2g})"
    if as_pct:
        return f"{dp.value:.0%}"
    return f"{dp.value:.2g}"


def _fmt_dt(dt: datetime | None, tz: ZoneInfo) -> str:
    if dt is None:
        return "n/a"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")


def render_html(payload: BriefPayload) -> str:
    r = payload.regime
    lines: list[str] = []
    lines.append(f"<b>Market Brief — {payload.trading_date}</b>")
    lines.append(f"<i>Generated {_fmt_dt(payload.generated_at, NY)}</i>")
    if payload.degraded:
        lines.append("<b>⚠ Degraded</b> (collector errors)")
    lines.append("")
    lines.append(f"<b>Regime:</b> {r.label.value}")
    lines.append(f"Exposure ceiling: {r.exposure_ceiling_pct}% | Score: {r.score_sum}")
    if r.reasons:
        lines.append("Signals: " + "; ".join(r.reasons[:6]))
    lines.append("")
    lines.append("<b>Key levels</b>")
    snap = payload.snapshot
    rows = [
        ("VIX", snap.vix),
        ("VIX3M", snap.vix3m),
        ("VIX/VIX3M", snap.vix_term_ratio),
        ("HY OAS", snap.hy_oas),
        ("HY OAS z252", snap.hy_oas_zscore_252d),
        ("10Y-2Y", snap.yield_curve_10y2y),
        ("SPX", snap.spx),
        ("SPX vs 50DMA %", snap.spx_vs_50dma_pct),
        ("SPX vs 200DMA %", snap.spx_vs_200dma_pct),
        ("Sector breadth", snap.sector_breadth),
        ("RSP/SPY 20d rel %", snap.rsp_spy_20d_rel_pct),
    ]
    lines.append("<pre>")
    for name, dp in rows:
        pct = "breadth" in name.lower()
        lines.append(f"{name:22} {_fmt_value(dp, as_pct=pct):>12}  [{dp.status.value}]")
    lines.append("</pre>")
    lines.append("")
    lines.append("<b>Calendar</b>")
    if not payload.calendar:
        lines.append("<i>No curated events (see events.yaml / Phase 2 live feed)</i>")
    else:
        lines.append("<pre>")
        for ev in payload.calendar[:12]:
            lines.append(
                f"{ev.title[:40]:40} | Sofia: {_fmt_dt(ev.start_utc, SOFIA)} | "
                f"UTC: {_fmt_dt(ev.start_utc, ZoneInfo('UTC'))}"
            )
        lines.append("</pre>")
    lines.append("")
    lines.append("<b>Commentary</b>")
    lines.append(f"<b>{payload.narrative.headline}</b>")
    lines.append("<ul>")
    for b in payload.narrative.bullets:
        lines.append(f"<li>{b}</li>")
    lines.append("</ul>")
    lines.append("")
    lines.append("<i>Deterministic metrics; LLM commentary only. Not investment advice.</i>")
    if payload.collector_errors:
        lines.append("<pre>Errors: " + "; ".join(payload.collector_errors) + "</pre>")
    return "\n".join(lines)


def split_telegram_messages(html: str, limit: int = 4096) -> list[str]:
    if len(html) <= limit:
        return [html]
    parts: list[str] = []
    chunk = ""
    for line in html.split("\n"):
        if len(chunk) + len(line) + 1 > limit:
            parts.append(chunk)
            chunk = line + "\n"
        else:
            chunk += line + "\n"
    if chunk:
        parts.append(chunk)
    return parts
