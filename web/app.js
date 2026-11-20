const briefRoot = document.getElementById("brief-root");
const sampleBanner = document.getElementById("sample-banner");
const asOf = document.getElementById("as-of");
const provenance = document.getElementById("provenance");
const viewerEl = document.getElementById("viewer");

function showError(message) {
  briefRoot.innerHTML = `<p class="error">${message}</p>`;
  briefRoot.setAttribute("aria-busy", "false");
}

function formatGeneratedAt(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      timeZone: "America/New_York",
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function provenanceLines(payload) {
  const lines = [];
  const snap = payload?.snapshot;
  if (!snap) return lines;
  const check = (name, dp) => {
    if (dp && dp.status && dp.status !== "OK") {
      lines.push(`${name}: ${dp.status}`);
    }
  };
  check("VIX", snap.vix);
  check("SPX", snap.spx);
  check("HY OAS", snap.hy_oas);
  for (const block of payload.gex_symbols || []) {
    check(`${block.display_symbol} net GEX`, block.net_gex);
    check(`${block.display_symbol} spot`, block.spot);
  }
  if (payload.degraded) {
    lines.unshift("Degraded run");
  }
  return lines;
}

async function loadViewer() {
  try {
    const res = await fetch("/api/viewer", { credentials: "same-origin" });
    if (!res.ok) return;
    const data = await res.json();
    if (data?.name) {
      viewerEl.textContent = `Signed in as ${data.name}`;
      viewerEl.classList.remove("hidden");
    }
  } catch {
    /* static local preview — no API */
  }
}

async function main() {
  let snapshot;
  try {
    const snapRes = await fetch("snapshot.json", { cache: "no-store" });
    if (!snapRes.ok) throw new Error(`snapshot.json (${snapRes.status})`);
    snapshot = await snapRes.json();
  } catch (err) {
    showError(`Could not load snapshot.json — ${err.message}`);
    return;
  }

  const { meta, payload } = snapshot;
  if (meta?.mode === "sample" && meta?.label) {
    sampleBanner.textContent = meta.label;
    sampleBanner.classList.remove("hidden");
  }
  if (payload?.trading_date) {
    const gen = formatGeneratedAt(payload.generated_at);
    asOf.textContent = `Trade date ${payload.trading_date}${gen ? ` · generated ${gen} ET` : ""}`;
  }
  const prov = provenanceLines(payload);
  if (meta?.source) {
    prov.push(`Source: ${meta.source}`);
  }
  provenance.textContent = prov.length ? prov.join(" · ") : "All core fields OK in snapshot.";

  try {
    const htmlRes = await fetch("brief.html", { cache: "no-store" });
    if (!htmlRes.ok) throw new Error(`brief.html (${htmlRes.status})`);
    const html = await htmlRes.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const wrap = doc.querySelector(".wrap");
    briefRoot.innerHTML = "";
    if (wrap) {
      briefRoot.appendChild(document.adoptNode(wrap));
    } else {
      const body = doc.body;
      briefRoot.innerHTML = body ? body.innerHTML : html;
    }
    briefRoot.setAttribute("aria-busy", "false");
  } catch (err) {
    showError(`Could not load brief.html — ${err.message}`);
  }

  await loadViewer();
}

main();