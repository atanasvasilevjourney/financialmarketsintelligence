from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from brief.collectors.base import BaseCollector

# TODO(Phase 2): optional live macro calendar adapter (e.g. paid API or scrape with approval).
DEFAULT_EVENTS_PATH = Path(__file__).resolve().parents[3] / "config" / "events.yaml"


class CalendarCollector(BaseCollector):
    name = "calendar"

    def __init__(
        self,
        events_path: Path | None = None,
        stale_after_minutes: int = 360,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.events_path = events_path or DEFAULT_EVENTS_PATH
        self.stale_after_minutes = stale_after_minutes

    def collect(self) -> dict[str, Any]:
        raw = yaml.safe_load(self.events_path.read_text(encoding="utf-8")) or {}
        events_raw = raw.get("events") or []
        events: list[dict[str, Any]] = []
        for item in events_raw:
            start = item.get("start_utc")
            if isinstance(start, str):
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            elif isinstance(start, datetime):
                start_dt = start
            else:
                continue
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            events.append(
                {
                    "title": str(item.get("title", "Event")),
                    "start_utc": start_dt,
                    "importance": str(item.get("importance", "medium")),
                    "source": str(item.get("source", "events.yaml")),
                }
            )
        return {
            "events": events,
            "stale_after_minutes": self.stale_after_minutes,
            "source": "events.yaml",
            "as_of": datetime.now(UTC),
        }
