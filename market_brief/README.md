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

## Collectors

| Module | Source | Notes |
|--------|--------|-------|
| `collectors/markets.py` | yfinance | VIX, VIX3M, SPX, 50/200 DMA distances |
| `collectors/fred.py` | FRED API | HY OAS + 252d z-score, T10Y2Y |
| `collectors/sectors.py` | yfinance | Sector ETF breadth, RSP/SPY 20d relative |
| `collectors/calendar.py` | `config/events.yaml` | **TODO Phase 2:** live macro calendar adapter |

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

## Phase 2 extension points

- Live macro calendar collector (replace/augment `events.yaml`)
- GEX / put-call / dealer positioning modules
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
