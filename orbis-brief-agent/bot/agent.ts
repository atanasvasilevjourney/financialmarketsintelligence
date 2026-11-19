import { defineAgent } from "@grok/agent-sdk";

import { fmiRepoRoot } from "./lib/paths.js";

export default defineAgent({
  model: {
    id: "grok-4.7",
    params: [
      { id: "reasoning_effort", value: "high" },
      { id: "fast", value: "true" },
    ],
  },
  local: {
    /** FMI monorepo root so brief subprocess + repo rules resolve in local dev. */
    cwd: fmiRepoRoot(),
  },
  hosting: {
    egressDomains: [
      "api.stlouisfed.org",
      "orbis-gex.onrender.com",
      "query1.finance.yahoo.com",
      "query2.finance.yahoo.com",
    ],
    secretNames: [
      "MARKET_BRIEF_ROOT",
      "BRIEF_DATA_DIR",
      "FRED_API_KEY",
      "ORBIS_SIDECAR_URL",
      "ORBIS_SIDECAR_TIMEOUT_SEC",
      "DISCORD_WEBHOOK_URL",
      "TELEGRAM_BOT_TOKEN",
      "TELEGRAM_CHAT_ID",
      "ANTHROPIC_API_KEY",
      "BRIEF_LANG",
    ],
  },
});