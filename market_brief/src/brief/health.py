from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def ping_failure(message: str) -> None:
    url = os.environ.get("HEALTHCHECK_URL")
    if not url:
        logger.warning("HEALTHCHECK_URL not set; failure not pinged: %s", message)
        return
    try:
        httpx.get(f"{url}/fail", timeout=10.0)
    except httpx.HTTPError as exc:
        logger.error("Healthcheck ping failed: %s", exc)


def ping_success() -> None:
    url = os.environ.get("HEALTHCHECK_URL")
    if not url:
        return
    try:
        httpx.get(url, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.error("Healthcheck success ping failed: %s", exc)
