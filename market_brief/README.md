# market-brief (Phase 1)

Deterministic daily market-sentiment brief with optional LLM commentary and Telegram/Discord delivery.

## Principles

- All market numbers are computed in Python collectors; the LLM only narrates from validated JSON.
- Every datapoint carries `value`, `as_of` (UTC), `source`, `stale_after_minutes`, and `status` (`OK` | `STALE` | `MISSING`).
- One collector failure degrades the brief; total failure pings healthchecks and exits non-zero.

## Setup

Requirements: **Python 3.12+**

```bash
cd market_brief
python -m pip install -U pip
python -m pip install -e ".[dev]"
cp .env.example .env   # fill secrets locally; never commit .env
```

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FRED_API_KEY` | Live FRED data | HY OAS (`BAMLH0A0HYM2`), 10y-2y (`T10Y2Y`) |
| `ANTHROPIC_API_KEY` | Optional | LLM commentary (skip with `--no-llm`) |
| `BRIEF_LANG` | Optional | Default `bg` |
| `BRIEF_MODEL` | Optional | Anthropic model id |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Live Telegram | Acceptance criterion #2 |
| `DISCORD_WEBHOOK_URL` | Optional | Discord delivery |
| `HEALTHCHECK_URL` | Optional | [Healthchecks.io](https://healthchecks.io) fail/success pings |
| `BRIEF_DATA_DIR` | Optional | Snapshots & idempotency markers (default `./data`) |
| `ORBIS_SIDECAR_URL` | Optional | ORBIS GEX HTTP sidecar base URL |
| `ORBIS_SIDECAR_TIMEOUT_SEC` | Optional | Sidecar HTTP timeout (default **90**; use on cold Render / OpEx days) |
| `ORBIS_SIDECAR_WARMUP` | Optional | `1` = best-effort `GET /health` before daily GEX fetch (default on) |

## Run

```bash
# Offline-safe (tests use fixtures); live yfinance + FRED when keys/network available
python -m brief run --dry-run --no-llm --skip-window-check

# Production-style (requires Telegram secrets for delivery)
python -m brief run --skip-window-check
```

Flags:

- `--dry-run` — write HTML + JSON snapshot, no Telegram/Discord
- `--no-llm` — template commentary (CI default)
- `--force` — ignore per-day idempotency marker
- `--skip-window-check` — bypass 07:30–08:30 America/New_York scheduler guard
- `--orbis-html` — write ORBIS-branded mobile HTML snapshot (+ Telegram summary when delivering)

## Collectors

| Module | Source | Notes |
|--------|--------|-------|
| `collectors/markets.py` | yfinance | VIX, VIX3M, SPX, 50/200 DMA distances |
| `collectors/fred.py` | FRED API | HY OAS + 252d z-score, T10Y2Y |
| `collectors/sectors.py` | yfinance | Sector ETF breadth, RSP/SPY 20d relative |
| `collectors/calendar.py` | `config/events.yaml` | Curated events; live macro calendar → Phase 2 TODO |
| `collectors/gex_orbis.py` | ORBIS sidecar HTTP | Warm-up `/health`, `ORBIS_SIDECAR_TIMEOUT_SEC` (default 90s), SPY/QQQ → SPX/NDX |
| `collectors/markets.py` | yfinance | Adds **ES=F / NQ=F** for KPI strip |
| `config/desk_sources.yaml` | Curated YAML | Desk themes + URLs → `desk_context[]` (no scraped numbers) |
| `opex_calendar.py` | Heuristic | Monthly index OpEx badge (third Friday; NYSE weekdays) |

### Adding a collector

1. Subclass `collectors.base.BaseCollector` and implement `collect()`.
2. Return a dict with `{field: {value, as_of}, source, stale_after_minutes}`.
3. Wire into `pipeline._build_snapshot` and `config/thresholds.yaml` if used for regime.
4. Add JSON fixtures under `tests/fixtures/` and inject via `inject=` in tests (no network in CI).

## Regime engine

Reads `config/thresholds.yaml`. Signals map to scores `{-1,0,+1}`; sum maps to `RISK_ON` / `NEUTRAL` / `CAUTION` / `RISK_OFF`. More than two missing inputs → `INSUFFICIENT_DATA` (0% exposure ceiling).

## Assumptions (Phase 1)

- yfinance end-of-day data is acceptable for VIX/SPX/sectors (not a licensed real-time feed).
- FRED HY OAS may lag; `stale_after_minutes.fred` defaults to 1440.
- Economic calendar is curated YAML only until a vetted live source is integrated.
- LLM model id defaults to `claude-sonnet-4-20250514` (override via `BRIEF_MODEL`); spec target Sonnet 5.5 when available in API.
- Scheduled GitHub Actions cannot receive Telegram without repository secrets — **criterion #2 requires you to add `TELEGRAM_*` secrets**; the workflow will not DM you until then.

## GitHub Actions keepalive

Private repos disable scheduled workflows after ~60 days of repository inactivity. To keep the daily brief cron alive:

- Merge occasional commits, or
- Manually run **Daily market brief** via `workflow_dispatch`, or
- Add a lightweight monthly noop workflow / external ping.

Dual crons in `.github/workflows/brief.yml` cover EST and EDT for ~07:35 New York.

## Phase 2 (ORBIS GEX scaffold)

Phase 2 adds an ORBIS-branded mobile HTML path and a thin HTTP collector to the existing sidecar — **not** a full GEX reimplementation or backtest.

### ORBIS sidecar collector

| Module | Source | Notes |
|--------|--------|-------|
| `collectors/gex_orbis.py` | `ORBIS_SIDECAR_URL` (default `https://orbis-gex.onrender.com`) | `GET /daily/SPY/latest` and `/daily/QQQ/latest`, mapped to **SPX** / **NDX** labels in payload + HTML |

Set `ORBIS_SIDECAR_URL` in CI/production; tests inject `tests/fixtures/gex.json` (no network).

### ORBIS HTML render

| Module | Role |
|--------|------|
| `render/orbis_html.py` | Mobile HTML aligned with ORBIS Daily Brief UI spec — **all numbers from `BriefPayload` only** |
| `render/market_html.py` | Phase 1 Telegram HTML (unchanged behaviour) |

Run with:

```bash
python -m brief run --dry-run --no-llm --skip-window-check --orbis-html
```

Writes `data/orbis_brief_{trade_date}.html`. With Telegram delivery, `--orbis-html` sends a **short summary** plus path/link (`ORBIS_HTML_PUBLIC_URL` optional).

Extended payload fields: `gex_symbols`, `exposure_footer`, `technicals_es` (placeholders OK as `MISSING`), `kpi_strip` (ES/NQ from futures; equity P/C TODO), `opex_badge`, `opex_flow` stub, `desk_context`, `alignment_summary`.

### Where the brief publishes

See project docs `brief-publication-channels.md`: **Telegram primary**, optional Discord, HTML snapshot on disk/runner — **not** a public website unless you host the HTML yourself.

### Phase 2 TODO (not in this scaffold)

- Global overnight index table collector
- High-impact earnings (after-hours) adapter
- Equity put/call ratio collector
- NYSE / custom breadth CSV feed
- Live macro calendar (replace `events.yaml` only)
- VOLATILITY / MACRO / SIGNAL narrative cards (separate LLM sections; Phase 1 single narrative block)
- Full parity with `orbis_gex` `brief-template.html` (hosted static deploy)
- Regime / GEX historical backtest

## Phase 3+ ideas

- Web UI and historical backtest of regime labels
- Richer breadth (NYSE % above MA) via a licensed feed

## Development

```bash
ruff check src tests
mypy src/brief
pytest
```

Tests use fixtures only — no network in CI.

## Layout

```
config/           thresholds + curated events
src/brief/        package (`python -m brief`)
tests/            pytest + fixtures
```

Not investment advice.
