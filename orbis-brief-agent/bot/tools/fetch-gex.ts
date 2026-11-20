import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

import {
  defaultSidecarBase,
  normalizeDailyGex,
  sidecarTimeoutMs,
} from "../lib/gex-normalize.js";
import type { JsonValue } from "../lib/paths.js";

export default defineTool({
  description: prompt`
    Fetch latest ORBIS GEX daily levels for SPY or QQQ from the HTTP sidecar.
    Returns normalized JSON aligned with market_brief collectors — use only these values in replies.
  `,
  effect: "read",
  inputSchema: z.object({
    symbol: z.enum(["SPY", "QQQ"]).describe("Upstream ETF symbol."),
  }),
  async execute({ symbol }) {
    const base = defaultSidecarBase();
    const endpoint = `${base}/daily/${symbol}/latest`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), sidecarTimeoutMs());
    try {
      const res = await fetch(endpoint, {
        signal: controller.signal,
        headers: { accept: "application/json" },
      });
      if (!res.ok) {
        return {
          ok: false as const,
          symbol,
          endpoint,
          status: res.status,
          error: `Sidecar HTTP ${res.status}`,
        };
      }
      const raw = (await res.json()) as Record<string, unknown>;
      const normalized = normalizeDailyGex(raw, symbol);
      return {
        ok: true as const,
        symbol,
        endpoint,
        normalized,
        raw: raw as unknown as JsonValue,
      };
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Sidecar request failed";
      return {
        ok: false as const,
        symbol,
        endpoint,
        error: message,
      };
    } finally {
      clearTimeout(timer);
    }
  },
});