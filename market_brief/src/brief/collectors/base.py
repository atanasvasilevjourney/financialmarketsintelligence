from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class CollectorError(Exception):
    """Raised when a collector cannot produce data."""


class BaseCollector(ABC):
    name: str

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> BaseCollector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """Return collector-specific raw payload for downstream normalization."""
