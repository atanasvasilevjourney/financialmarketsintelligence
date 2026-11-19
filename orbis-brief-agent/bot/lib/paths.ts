import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = path.dirname(fileURLToPath(import.meta.url));

/** `orbis-brief-agent/` project root (parent of `bot/`). */
export function agentProjectRoot(): string {
  return path.resolve(moduleDir, "../..");
}

/** Sibling `market_brief/` package directory in the FMI monorepo. */
export function defaultMarketBriefRoot(): string {
  return path.resolve(agentProjectRoot(), "../market_brief");
}

/** Hosted override: absolute path to `market_brief/` on the serve host. */
export function marketBriefRoot(): string {
  const env = process.env.MARKET_BRIEF_ROOT?.trim();
  if (env) return path.resolve(env);
  return defaultMarketBriefRoot();
}

export function resolveBriefDataDir(): string {
  const env = process.env.BRIEF_DATA_DIR?.trim();
  if (env) return path.resolve(env);
  const live = path.join(marketBriefRoot(), "data");
  if (existsSync(live)) return live;
  return path.join(agentProjectRoot(), "evals/fixtures");
}

export function fmiRepoRoot(): string {
  return path.resolve(agentProjectRoot(), "..");
}

/** JSON values returned from tools (Agent SDK tool result contract). */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };