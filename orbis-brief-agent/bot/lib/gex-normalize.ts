type GexField = {
  value: number | null;
  label?: string;
  as_of: string | null;
  source: string;
};

export type NormalizedGexSymbol = {
  symbol: string;
  source: string;
  stale: boolean;
  as_of: string | null;
  spot?: GexField;
  net?: GexField;
  flip?: GexField;
  callWall?: GexField;
  putWall?: GexField;
  maxPain?: GexField;
  regime?: GexField;
};

export type NormalizedGexResponse = {
  symbol: string;
  endpoint: string;
  normalized: NormalizedGexSymbol;
  raw: Record<string, unknown>;
};

function parseAsOf(body: Record<string, unknown>): string | null {
  const raw = body.as_of ?? body.asOf ?? body.trade_date ?? body.tradeDate;
  if (typeof raw === "string" && raw.length > 0) return raw;
  return null;
}

function fieldFrom(
  val: unknown,
  asOf: string | null,
  source: string,
  asLabel = false,
): GexField | undefined {
  if (val === null || val === undefined) return undefined;
  if (asLabel) {
    return { value: null, label: String(val), as_of: asOf, source };
  }
  if (typeof val === "number") {
    return { value: val, as_of: asOf, source };
  }
  if (typeof val === "string") {
    const n = Number(val);
    if (!Number.isNaN(n)) return { value: n, as_of: asOf, source };
    return { value: null, label: val, as_of: asOf, source };
  }
  if (typeof val === "object" && val !== null && "value" in val) {
    const o = val as { value?: unknown; label?: unknown };
    return {
      value: typeof o.value === "number" ? o.value : null,
      label: o.label !== undefined ? String(o.label) : undefined,
      as_of: asOf,
      source,
    };
  }
  return { value: null, label: String(val), as_of: asOf, source };
}

/** Align sidecar camelCase JSON with `market_brief` collector shape. */
export function normalizeDailyGex(
  body: Record<string, unknown>,
  symbol: string,
): NormalizedGexSymbol {
  const asOf = parseAsOf(body);
  const stale = Boolean(body.stale ?? body.is_stale ?? body.isStale);
  const source = String(body.source ?? "orbis_sidecar");

  const out: NormalizedGexSymbol = {
    symbol,
    source,
    stale,
    as_of: asOf,
  };

  const spot = fieldFrom(body.spot, asOf, source);
  const net = fieldFrom(
    body.net ?? body.netGex ?? body.net_gex,
    asOf,
    source,
  );
  const flip = fieldFrom(
    body.flip ?? body.zeroGamma ?? body.zero_gamma,
    asOf,
    source,
  );
  const callWall = fieldFrom(
    body.callWall ?? body.call_wall,
    asOf,
    source,
  );
  const putWall = fieldFrom(body.putWall ?? body.put_wall, asOf, source);
  const maxPain = fieldFrom(
    body.maxPain ?? body.max_pain,
    asOf,
    source,
  );
  const regime = fieldFrom(
    body.regime ?? body.gamma_regime,
    asOf,
    source,
    true,
  );

  if (spot) out.spot = spot;
  if (net) out.net = net;
  if (flip) out.flip = flip;
  if (callWall) out.callWall = callWall;
  if (putWall) out.putWall = putWall;
  if (maxPain) out.maxPain = maxPain;
  if (regime) out.regime = regime;

  return out;
}

export function defaultSidecarBase(): string {
  return (
    process.env.ORBIS_SIDECAR_URL?.replace(/\/$/, "") ??
    "https://orbis-gex.onrender.com"
  );
}

export function sidecarTimeoutMs(): number {
  const raw = process.env.ORBIS_SIDECAR_TIMEOUT_SEC ?? "90";
  const sec = Math.max(5, Number.parseFloat(raw) || 90);
  return Math.round(sec * 1000);
}