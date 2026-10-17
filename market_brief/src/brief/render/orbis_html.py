from __future__ import annotations

import os
from zoneinfo import ZoneInfo

from brief.models import BriefPayload, DataPoint, DataStatus, KpiStrip

NY = ZoneInfo("America/New_York")


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_num(dp: DataPoint, *, suffix: str = "", billions: bool = False) -> str:
    if dp.status == DataStatus.MISSING or dp.value is None:
        if dp.label:
            return _esc(dp.label)
        return "n/a"
    val = dp.value
    if billions:
        val = val / 1e9
        text = f"{val:+.2f}B"
    elif abs(val) >= 1000:
        text = f"{val:,.2f}"
    elif abs(val) < 10:
        text = f"{val:.2f}"
    else:
        text = f"{val:.1f}"
    if dp.status == DataStatus.STALE:
        text = f"STALE {text}"
    return _esc(text + suffix)


def _fmt_pct(dp: DataPoint) -> str:
    if dp.status == DataStatus.MISSING or dp.value is None:
        return "n/a"
    text = f"{dp.value:+.2f}%"
    if dp.status == DataStatus.STALE:
        text = f"STALE {text}"
    return _esc(text)


def _fmt_regime_tag(dp: DataPoint) -> str:
    if dp.label:
        return _esc(dp.label.upper())
    if dp.value is not None:
        return _esc(str(dp.value))
    return "n/a"


def _date_header(payload: BriefPayload) -> str:
    dt = payload.generated_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    local = dt.astimezone(NY)
    return local.strftime("%A • %d %b %Y").upper()


def _provenance(payload: BriefPayload) -> list[str]:
    lines: list[str] = []
    snap = payload.snapshot
    for name, dp in (
        ("VIX", snap.vix),
        ("SPX", snap.spx),
        ("HY OAS", snap.hy_oas),
    ):
        if dp.status != DataStatus.OK:
            lines.append(f"{name}: {dp.status.value}")
    for block in payload.gex_symbols:
        for label, dp in (
            (f"{block.display_symbol} net GEX", block.net_gex),
            (f"{block.display_symbol} spot", block.spot),
        ):
            if dp.status != DataStatus.OK:
                lines.append(f"{label}: {dp.status.value}")
    if payload.technicals_es:
        t = payload.technicals_es
        if t.rsi.status == DataStatus.MISSING:
            lines.append("Technicals RSI: MISSING")
    return lines


def _kpi_strip(payload: BriefPayload) -> KpiStrip:
    if payload.kpi_strip is not None:
        return payload.kpi_strip
    miss = DataPoint(label="n/a", source="n/a", stale_after_minutes=60, status=DataStatus.MISSING)
    return KpiStrip(es=miss, nq=miss, vix=payload.snapshot.vix, put_call=miss)


def render_orbis_html(payload: BriefPayload) -> str:
    snap = payload.snapshot
    kpi = _kpi_strip(payload)
    footer = payload.exposure_footer
    regime = payload.regime

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8"/>')
    parts.append(
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
    )
    parts.append("<title>ORBIS GEX — Daily Brief</title>")
    parts.append("<style>")
    parts.append(
        """
:root { --bg:#0b0f14; --card:#121820; --muted:#8b9cb3; --text:#e8eef7;
  --vol:#7c5cff; --macro:#00b894; --signal:#f39c12; --accent:#3d8bfd; }
* { box-sizing:border-box; }
body { margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg);
  color:var(--text); line-height:1.45; font-size:15px; }
.wrap { max-width:480px; margin:0 auto; padding:12px 14px 32px; }
.hdr { text-align:center; padding:16px 8px; border-bottom:1px solid #1e2836; }
.hdr h1 { font-size:1.05rem; letter-spacing:.12em; margin:0 0 4px; }
.hdr .sub { color:var(--accent); font-size:.75rem; letter-spacing:.2em; }
.hdr .date { color:var(--muted); font-size:.8rem; margin-top:8px; }
.kpi { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin:14px 0; }
.kpi div { background:var(--card); border-radius:8px; padding:8px 4px; text-align:center; }
.kpi span { display:block; font-size:.65rem; color:var(--muted); }
.kpi strong { font-size:.95rem; }
.card { border-left:4px solid var(--vol); background:var(--card); border-radius:0 10px 10px 0;
  padding:12px 14px; margin:10px 0; }
.card.macro { border-color:var(--macro); }
.card.signal { border-color:var(--signal); }
.card h3 { margin:0 0 6px; font-size:.72rem; letter-spacing:.15em; color:var(--muted); }
section { margin:18px 0; }
section h2 { font-size:.78rem; letter-spacing:.14em; color:var(--accent); margin:0 0 8px; }
table { width:100%; border-collapse:collapse; font-size:.85rem; }
td, th { padding:6px 4px; border-bottom:1px solid #1e2836; text-align:left; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.footer-strip { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-top:20px;
  padding-top:14px; border-top:1px solid #1e2836; }
.footer-strip div { text-align:center; font-size:.72rem; }
.footer-strip strong { display:block; font-size:.85rem; margin-top:2px; }
.degraded { background:#3d1f1f; color:#ffb4b4; padding:8px 12px; border-radius:8px;
  font-size:.85rem; margin:10px 0; }
.provenance { color:var(--muted); font-size:.72rem; margin-top:16px; }
"""
    )
    parts.append("</style></head><body><div class=\"wrap\">")

    parts.append('<header class="hdr">')
    parts.append("<h1>ORBIS GEX — Daily Brief</h1>")
    parts.append('<div class="sub">PRE-MARKET BRIEF</div>')
    parts.append(f'<div class="date">{_esc(_date_header(payload))}</div>')
    gen = payload.generated_at.astimezone(NY).strftime("%Y-%m-%d %H:%M %Z")
    parts.append(f'<div class="date">Generated {_esc(gen)}</div>')
    parts.append("</header>")

    if payload.degraded:
        parts.append('<div class="degraded">⚠ Degraded run — see provenance for STALE/MISSING sources.</div>')

    parts.append('<div class="kpi">')
    for label, dp in (
        ("ES", kpi.es),
        ("NQ", kpi.nq),
        ("VIX", kpi.vix),
        ("P/C", kpi.put_call),
    ):
        parts.append("<div>")
        parts.append(f"<span>{label}</span>")
        parts.append(f"<strong>{_fmt_num(dp) if label != 'P/C' else _fmt_num(dp)}</strong>")
        parts.append("</div>")
    parts.append("</div>")

    bullets = payload.narrative.bullets or ["No commentary (--no-llm or narrative pending)."]
    card_titles = ("VOLATILITY", "MACRO", "SIGNAL")
    card_classes = ("", "macro", "signal")
    for i, title in enumerate(card_titles):
        text = bullets[i % len(bullets)]
        parts.append(f'<article class="card {card_classes[i]}">')
        parts.append(f"<h3>{title}</h3>")
        parts.append(f"<p>{_esc(text)}</p>")
        parts.append("</article>")

    parts.append("<section><h2>INDICES</h2><table>")
    parts.append("<tr><th>Symbol</th><th class=\"num\">Level</th><th class=\"num\">vs prior</th></tr>")
    for sym, dp, chg in (
        ("SPX", snap.spx, snap.spx_vs_50dma_pct),
        ("VIX", snap.vix, None),
    ):
        chg_txt = _fmt_pct(chg) if chg else "—"
        parts.append(
            f"<tr><td>{sym}</td><td class=\"num\">{_fmt_num(dp)}</td>"
            f"<td class=\"num\">{chg_txt}</td></tr>"
        )
    parts.append("</table></section>")

    parts.append("<section><h2>MARKET REGIME</h2>")
    parts.append(f"<p><strong>{_esc(regime.label.value)}</strong> · score {regime.score_sum}</p>")
    breadth = snap.sector_breadth
    parts.append(
        f"<p>Breadth {_fmt_pct(breadth)} [{breadth.status.value}] · "
        f"source {_esc(breadth.source)}</p>"
    )
    if regime.reasons:
        parts.append(f"<p>Top risks: {_esc('; '.join(regime.reasons[:3]))}</p>")
    parts.append("</section>")

    parts.append("<section><h2>EXPOSURE DECISION</h2>")
    if footer:
        parts.append(
            f"<p>Net exposure ceiling <strong>{footer.exposure_pct}%</strong> · "
            f"Bias <strong>{_esc(footer.bias)}</strong> · "
            f"New entries: <strong>{_esc(footer.new_entries)}</strong></p>"
        )
        if footer.reasoning:
            parts.append("<ul>")
            for r in footer.reasoning:
                parts.append(f"<li>{_esc(r)}</li>")
            parts.append("</ul>")
    parts.append("</section>")

    parts.append("<section><h2>TECHNICALS · ES DAILY</h2><table>")
    t = payload.technicals_es
    if t:
        rows = (
            ("vs 20 DMA", t.vs_20dma_pct),
            ("vs 50 DMA", t.vs_50dma_pct),
            ("vs 200 DMA", t.vs_200dma_pct),
            ("RSI", t.rsi),
            ("MACD", t.macd_state),
            ("ATR", t.atr),
            ("Bollinger", t.bollinger_position),
        )
        for name, dp in rows:
            val = _fmt_pct(dp) if "DMA" in name else _fmt_num(dp)
            if dp.label and dp.value is None:
                val = _esc(dp.label)
            parts.append(
                f"<tr><td>{name}</td><td class=\"num\">{val}</td>"
                f"<td class=\"num\">[{dp.status.value}]</td></tr>"
            )
    else:
        parts.append("<tr><td colspan=\"3\">Technicals not collected (Phase 2 placeholder)</td></tr>")
    parts.append("</table></section>")

    parts.append("<section><h2>GEX · OPTIONS GREEKS</h2>")
    if not payload.gex_symbols:
        parts.append("<p>GEX data MISSING (orbis sidecar unavailable)</p>")
    for block in payload.gex_symbols:
        parts.append(f"<h3>{_esc(block.display_symbol)} "
                      f"<small>({_esc(block.upstream_symbol)})</small></h3>")
        parts.append("<table>")
        gex_rows: tuple[tuple[str, DataPoint, bool], ...] = (
            ("Net GEX", block.net_gex, True),
            ("Gamma regime", block.gamma_regime, False),
            ("Call wall", block.call_wall, False),
            ("Put wall", block.put_wall, False),
            ("Zero gamma", block.zero_gamma, False),
            ("Spot", block.spot, False),
        )
        for name, dp, billions in gex_rows:
            if name == "Gamma regime":
                val = _fmt_regime_tag(dp)
            else:
                val = _fmt_num(dp, billions=billions)
            parts.append(
                f"<tr><td>{name}</td><td class=\"num\">{val}</td>"
                f"<td class=\"num\">[{dp.status.value}]</td></tr>"
            )
        parts.append("</table>")
    parts.append("</section>")

    parts.append("<section><h2>SECTOR ROTATION · DAILY</h2>")
    parts.append(
        f"<p>Breadth {_fmt_pct(snap.sector_breadth)} · "
        f"RSP/SPY 20d {_fmt_pct(snap.rsp_spy_20d_rel_pct)}</p>"
    )
    if snap.sector_details:
        parts.append("<table><tr><th>ETF</th><th class=\"num\">Above 50 DMA</th></tr>")
        for sym, dp in sorted(snap.sector_details.items()):
            above = "yes" if dp.meta.get("above_50dma") else "no"
            parts.append(f"<tr><td>{sym}</td><td class=\"num\">{above} [{dp.status.value}]</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Sector detail table TODO (per-ETF session % bars)</p>")
    parts.append("</section>")

    parts.append("<section><h2>CALENDAR</h2>")
    if not payload.calendar:
        parts.append("<p>No curated events (live macro calendar TODO)</p>")
    else:
        parts.append("<ul>")
        for ev in payload.calendar[:8]:
            parts.append(f"<li>{_esc(ev.title)} · {_esc(ev.importance)}</li>")
        parts.append("</ul>")
    parts.append("<p>Tonight's earnings: TODO (high-impact filter)</p>")
    parts.append("<p>Global overnight indices: TODO</p>")
    parts.append("</section>")

    parts.append('<div class="footer-strip">')
    if footer:
        for label, val in (
            ("EXPOSURE %", str(footer.exposure_pct)),
            ("BIAS", footer.bias),
            ("REGIME", footer.regime_label),
            ("NEW ENTRIES", footer.new_entries),
        ):
            parts.append("<div>")
            parts.append(f"<span>{label}</span>")
            parts.append(f"<strong>{_esc(val)}</strong>")
            parts.append("</div>")
    parts.append("</div>")

    prov = _provenance(payload)
    if prov:
        parts.append('<div class="provenance">Data provenance: ' + _esc("; ".join(prov)) + "</div>")

    parts.append("</div></body></html>")
    return "\n".join(parts)


def telegram_orbis_summary(payload: BriefPayload, *, html_path: str | None = None) -> str:
    """Short Telegram HTML when full brief is delivered as ORBIS HTML file."""
    lines: list[str] = []
    lines.append("<b>ORBIS GEX — Daily Brief</b>")
    lines.append(f"<i>{payload.trading_date}</i>")
    if payload.degraded:
        lines.append("⚠ <b>Degraded</b>")
    r = payload.regime
    lines.append(f"Regime: {r.label.value} · Exposure ceiling {r.exposure_ceiling_pct}%")
    if payload.gex_symbols:
        for g in payload.gex_symbols:
            net = _fmt_num(g.net_gex, billions=True)
            lines.append(f"{g.display_symbol} net GEX: {net} · {_fmt_regime_tag(g.gamma_regime)}")
    else:
        lines.append("GEX: MISSING (sidecar)")
    lines.append("")
    lines.append(f"<b>{payload.narrative.headline or 'Summary'}</b>")
    for b in payload.narrative.bullets[:3]:
        lines.append(f"• {b}")
    lines.append("")
    if html_path:
        lines.append(f"📄 Full mobile brief HTML: <code>{html_path}</code>")
    link = os.environ.get("ORBIS_HTML_PUBLIC_URL")
    if link:
        lines.append(f'🔗 <a href="{link}">Open ORBIS brief</a>')
    return "\n".join(lines)
