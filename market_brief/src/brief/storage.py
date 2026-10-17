from __future__ import annotations

import json
import os
from pathlib import Path

from brief.models import BriefPayload


def data_dir() -> Path:
    raw = os.environ.get("BRIEF_DATA_DIR", "./data")
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshot_path(trading_date: str) -> Path:
    return data_dir() / f"brief_{trading_date}.json"


def already_sent(trading_date: str) -> bool:
    marker = data_dir() / f"sent_{trading_date}.marker"
    return marker.exists()


def mark_sent(trading_date: str) -> None:
    marker = data_dir() / f"sent_{trading_date}.marker"
    marker.write_text("ok", encoding="utf-8")


def save_snapshot(payload: BriefPayload) -> Path:
    path = snapshot_path(payload.trading_date)
    path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_snapshot(trading_date: str) -> BriefPayload | None:
    path = snapshot_path(trading_date)
    if not path.exists():
        return None
    return BriefPayload.model_validate_json(path.read_text(encoding="utf-8"))


def write_dry_run_html(trading_date: str, html: str) -> Path:
    path = data_dir() / f"dry_run_{trading_date}.html"
    path.write_text(html, encoding="utf-8")
    return path


def export_payload_debug(payload: BriefPayload) -> str:
    return json.dumps(payload.model_dump(mode="json"), indent=2, ensure_ascii=False)
