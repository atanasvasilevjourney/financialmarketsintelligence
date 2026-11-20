# ORBIS Daily Brief — hosted reader (`apps.grok.bot`)

Static reader for the **market_brief** ORBIS mobile HTML output (same data contract as `orbis_html.py`). Published with Cursor **`publish-app`** (`project_dir: web`).

## Snapshot data (current)

Committed **sample** snapshot only — no invented numbers:

| File | Role |
|------|------|
| `snapshot.json` | `BriefPayload` JSON + `meta.mode: "sample"` banner label |
| `brief.html` | Rendered by `render_orbis_html()` from test fixtures |

Regenerate after fixture or renderer changes:

```bash
pip install -e market_brief/
python3 web/scripts/generate_snapshot.py
```

## Local preview

```bash
cd web && python3 -m http.server 8765 --bind 127.0.0.1
```

Open http://127.0.0.1:8765/ — the sample banner and ORBIS brief body load from the committed files.

## Live refresh (not wired in this static shell)

Hosted secrets (declare only — values in Cursor dashboard):

- `FRED_API_KEY` — macro series for regime inputs
- `ORBIS_SIDECAR_URL` — GEX sidecar base URL
- `ORBIS_SIDECAR_TIMEOUT_SEC` / `ORBIS_SIDECAR_WARMUP` — sidecar client tuning
- `MARKET_BRIEF_ROOT` — path to `market_brief` if a future refresh worker runs off-monorepo

Until a refresh worker is added, the app displays the committed fixture snapshot only.