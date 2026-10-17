from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    for _key, val in list(data.items()):
        if isinstance(val, dict) and "as_of" in val:
            val["as_of"] = datetime.fromisoformat(val["as_of"])
    return data


@pytest.fixture
def fixture_inject() -> dict[str, dict]:
    return {
        "markets": _load("markets.json"),
        "fred": _load("fred.json"),
        "sectors": _load("sectors.json"),
        "calendar": {
            "events": [],
            "stale_after_minutes": 360,
            "source": "events.yaml",
            "as_of": datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
        },
    }


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 10, 16, 14, 0, tzinfo=UTC)
