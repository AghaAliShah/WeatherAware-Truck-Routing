"""Append-only JSONL telemetry for experiments (A/B events, shadow comparisons).

Every record is also emitted through the `telemetry` logger as one JSON line, so on
platforms with ephemeral disks (Hugging Face Spaces) the data is still recoverable
from the container logs."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("telemetry")
_lock = threading.Lock()


def _path(kind: str) -> Path:
    return Path(settings.TELEMETRY_DIR) / f"{kind}.jsonl"


def record(kind: str, payload: dict) -> None:
    """Write one record. Telemetry must never break a request, so all failures are swallowed."""
    line = json.dumps({"ts": round(time.time(), 3), "kind": kind, **payload}, separators=(",", ":"), default=str)
    logger.info(line)
    try:
        with _lock:
            path = _path(kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError:
        logger.warning("telemetry file write failed for %s", kind)
