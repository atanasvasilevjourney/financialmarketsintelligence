# ORBIS Brief Agent (`orbis-brief-agent`)

Hosted [Agent SDK](https://cursor.com/docs/bdk) bot for the FMI **market_brief** pipeline and ORBIS GEX sidecar. HTTP playground is the default channel; Discord cron delivery remains in GitHub Actions.

## Prerequisites

- **Node.js 22.13+** (never Bun)
- **Python 3.12+** with `market_brief` installed (`pip install -e ".[dev]"` from `../market_brief/`)
- Cursor API credential for model turns (`CURSOR_API_KEY` or `npx @grok/agent-sdk@0.6.0 login`)

## Local development

```bash
cd orbis-brief-agent
npm install
npx @grok/agent-sdk@0.6.0 validate --dir .
npx @grok/agent-sdk@0.6.0 info --dir . --json
npm run check

# Direct tool call (no model key required)
npx @grok/agent-sdk@0.6.0 tool call get-snapshot --dir . \
  --input '{"tradingDate":"2026-10-16"}'

npx @grok/agent-sdk@0.6.0 dev
# Playground: http://127.0.0.1:3000/playground

npx @grok/agent-sdk@0.6.0 eval --dir . --tag smoke
```

### Path overrides

| Variable | Purpose |
|----------|---------|
| `MARKET_BRIEF_ROOT` | Absolute path to `market_brief/` on the host (required off-monorepo). |
| `BRIEF_DATA_DIR` | Directory containing `brief_YYYY-MM-DD.json` (default: `market_brief/data` or `evals/fixtures`). |

## Tools

| Name | Effect | Description |
|------|--------|-------------|
| `run-brief` | write / idempotent | `python3 -m brief run` with `dryRun`, `deliver`, `orbisHtml` |
| `get-snapshot` | read | Load `brief_YYYY-MM-DD.json` |
| `fetch-gex` | read | `GET {ORBIS_SIDECAR_URL}/daily/{SPY\|QQQ}/latest` (90s timeout) |

## Secrets (Cursor hosting)

Set on the deployment (names declared in `bot/agent.ts` → `hosting.secretNames`):

- `FRED_API_KEY` — live macro series
- `ORBIS_SIDECAR_URL` — GEX sidecar base URL
- `MARKET_BRIEF_ROOT` — path to `market_brief` if not sibling layout
- `BRIEF_DATA_DIR` — shared snapshot directory (optional)
- `DISCORD_WEBHOOK_URL` / `TELEGRAM_*` — only if using `run_brief` with delivery (chat default is dry run)
- `ANTHROPIC_API_KEY` — LLM commentary when `useLlm: true`

Egress allowlist includes FRED, Yahoo Finance, and `orbis-gex.onrender.com`.

## Deploy

1. Push this folder on a branch in `financialmarketsintelligence`.
2. From your machine (with service account or login):  
   `npx @grok/agent-sdk@0.6.0 validate --dir orbis-brief-agent`  
   `npx @grok/agent-sdk@0.6.0 deploy --dir orbis-brief-agent --ref <sha>`
3. Manage at [Deployed Agents](https://cursor.com/dashboard/deployed-agents).

See the Agent SDK deploy skill for dry-run and secret binding workflows.

## Architecture doc

Project store: [`docs/orbis-grok-agent-plan.md`](../../cursor/stores/bc-01a148e1-e02b-72e7-b950-56b372aae6b1/docs/orbis-grok-agent-plan.md) (user Context).

## Layout

```
bot/agent.ts          defineAgent + hosting
bot/instructions.md   ORBIS identity & non-negotiables
bot/tools/            run_brief, get_snapshot, fetch_gex
bot/lib/              path + GEX normalization helpers
bot/schedules/PRE_MARKET_NY.stub.txt  cron notes (production in GitHub Actions)
evals/                smoke eval + fixtures
```

Not investment advice.