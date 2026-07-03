"""Lightweight observability helpers for structured logs and alert counters."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger("observability")

_COUNTERS: dict[str, int] = defaultdict(int)
_RECENT: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
_CONSECUTIVE: dict[str, int] = defaultdict(int)


def _now() -> float:
    return time.time()


def increment(name: str, amount: int = 1) -> int:
    _COUNTERS[name] += amount
    _RECENT[name].append(_now())
    return _COUNTERS[name]


def set_consecutive(name: str, success: bool) -> int:
    if success:
        _CONSECUTIVE[name] = 0
    else:
        _CONSECUTIVE[name] += 1
    return _CONSECUTIVE[name]


def get_counter(name: str) -> int:
    return _COUNTERS.get(name, 0)


def get_consecutive(name: str) -> int:
    return _CONSECUTIVE.get(name, 0)


def count_recent(name: str, window_seconds: float = 300.0) -> int:
    cutoff = _now() - window_seconds
    records = _RECENT.get(name)
    if not records:
        return 0
    while records and records[0] < cutoff:
        records.popleft()
    return len(records)


def snapshot() -> dict[str, Any]:
    return {
        "counters": dict(_COUNTERS),
        "consecutive": dict(_CONSECUTIVE),
        "recent5m": {key: count_recent(key, 300.0) for key in list(_RECENT.keys())},
    }


def log_event(event: str, level: str = "info", **fields: Any) -> None:
    payload = {"event": event, **fields}
    message = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)
