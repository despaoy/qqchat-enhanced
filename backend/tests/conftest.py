"""Pytest configuration for the QQ assistant backend test suite."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

collect_ignore_glob = [
    "security_test.py",
    "fault_injection_test.py",
]