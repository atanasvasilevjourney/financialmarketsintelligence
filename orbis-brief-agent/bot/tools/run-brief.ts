import { spawn } from "node:child_process";
import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

import { marketBriefRoot } from "../lib/paths.js";

const inputSchema = z.object({
  dryRun: z
    .boolean()
    .default(true)
    .describe("When true, --dry-run (no Discord/Telegram delivery)."),
  deliver: z
    .enum(["discord", "none", "auto", "telegram"])
    .default("none")
    .describe("Delivery channel passed to python brief CLI."),
  orbisHtml: z
    .boolean()
    .default(true)
    .describe("Write ORBIS-branded HTML snapshot."),
  useLlm: z
    .boolean()
    .default(false)
    .describe("When false, --no-llm (template commentary only)."),
  force: z
    .boolean()
    .default(false)
    .describe("Ignore per-day idempotency marker."),
});

type RunBriefInput = z.infer<typeof inputSchema>;

function buildArgv(input: RunBriefInput): string[] {
  const argv = ["run", "--skip-window-check", `--deliver=${input.deliver}`];
  if (input.dryRun) argv.push("--dry-run");
  if (!input.useLlm) argv.push("--no-llm");
  if (input.orbisHtml) argv.push("--orbis-html");
  if (input.force) argv.push("--force");
  return argv;
}

function runPythonBrief(argv: string[], cwd: string): Promise<{
  exitCode: number | null;
  stdout: string;
  stderr: string;
}> {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", ["-m", "brief", ...argv], {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      resolve({ exitCode: code, stdout, stderr });
    });
  });
}

export default defineTool({
  description: prompt`
    Run the Python market_brief pipeline (python3 -m brief run) in the FMI market_brief checkout.
    Requires host env: FRED_API_KEY, ORBIS_SIDECAR_URL, and delivery secrets when deliver is not none.
    Scheduled Discord delivery stays in GitHub Actions; use dryRun=true for manual chat triggers.
  `,
  inputSchema,
  effect: (input: RunBriefInput) =>
    input.dryRun || input.deliver === "none" ? "idempotent" : "write",
  dryRunResult: (input: RunBriefInput) => ({
    acknowledged: true,
    wouldRun: {
      cwd: marketBriefRoot(),
      command: `python3 -m brief ${buildArgv(input).join(" ")}`,
    },
  }),
  async execute(input: RunBriefInput) {
    const cwd = marketBriefRoot();
    const argv = buildArgv(input);
    try {
      const { exitCode, stdout, stderr } = await runPythonBrief(argv, cwd);
      return {
        ok: exitCode === 0,
        exitCode,
        cwd,
        argv,
        stdoutTail: stdout.slice(-4000),
        stderrTail: stderr.slice(-2000),
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        ok: false,
        cwd,
        argv,
        error: message,
        hint: "Ensure Python 3.12+, pip install -e market_brief, and MARKET_BRIEF_ROOT if not in monorepo layout.",
      };
    }
  },
});