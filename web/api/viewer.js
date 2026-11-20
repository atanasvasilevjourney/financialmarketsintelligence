import { getIdentity } from "../cursor/identity.js";

const jsonHeaders = {
  "cache-control": "private, no-store",
  "content-type": "application/json",
};

export async function GET(request) {
  const identity = await getIdentity(request);
  if (!identity.verified) {
    return new Response(JSON.stringify({ verified: false, reason: identity.reason }), {
      status: 200,
      headers: jsonHeaders,
    });
  }
  return new Response(
    JSON.stringify({
      verified: true,
      name: identity.name || identity.email || "Viewer",
      kind: identity.kind,
    }),
    { headers: jsonHeaders },
  );
}