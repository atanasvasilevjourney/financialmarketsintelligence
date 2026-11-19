import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

import { resolveBriefDataDir, type JsonValue } from "../lib/paths.js";

export default defineTool({
  description: prompt`
    Load a saved market brief JSON snapshot (brief_YYYY-MM-DD.json).
    Use this to answer questions about regime, levels, and GEX already collected.
    Never invent numbers — only fields present in the returned snapshot.
  `,
  effect: "read",
  inputSchema: z.object({
    tradingDate: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .describe("Trading date in YYYY-MM-DD (matches filename)."),
  }),
  async execute({ tradingDate }) {
    const dir = resolveBriefDataDir();
    const file = path.join(dir, `brief_${tradingDate}.json`);
    try {
      await access(file);
    } catch {
      return {
        found: false,
        tradingDate,
        path: file,
        dataDir: dir,
      };
    }
    const text = await readFile(file, "utf8");
    const snapshot = JSON.parse(text) as JsonValue;
    return {
      found: true,
      tradingDate,
      path: file,
      dataDir: dir,
      snapshot,
    };
  },
});