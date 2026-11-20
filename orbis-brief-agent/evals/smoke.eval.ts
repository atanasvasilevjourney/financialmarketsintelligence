import { defineEval, includes } from "@grok/agent-sdk/evals";

export default defineEval({
  tags: ["smoke"],
  description: "Operator can load a fixture brief snapshot via get_snapshot.",
  async test(t) {
    await t.send(
      'Call get-snapshot for trading date 2026-10-16 and confirm found=true. Reply in one short sentence.',
    );
    t.succeeded();
    t.calledTool("get-snapshot", {
      input: { tradingDate: "2026-10-16" },
    });
    t.check(t.reply, includes(/2026-10-16|NEUTRAL|fixture|snapshot/i));
  },
});