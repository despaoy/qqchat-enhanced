"""Local API smoke checks for mock-mode verification."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEMP_DIR = BACKEND_ROOT / ".test_tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MODEL_PROVIDER", "mock")
os.environ.setdefault("VLLM_ENABLED", "false")
os.environ.setdefault("VLLM_BASE_URLS", "")
os.environ.setdefault("VLLM_BASE_URL", "http://localhost:8001")
os.environ.setdefault("SECURITY_MIDDLEWARE_ENABLED", "false")
os.environ.setdefault("ASTRBOT_ENABLED", "true")
os.environ.setdefault("ASTRBOT_INTEGRATION_TOKEN", "local-verify-token")
os.environ.setdefault("INTEGRATION_SIGNATURE_REQUIRED", "false")
os.environ.setdefault("DATABASE_PATH", str(TEMP_DIR / "local_verify.db"))
os.environ.setdefault("QQCHAT_BACKEND_URL", "http://127.0.0.1:8000")
os.environ.setdefault("JWT_SECRET", "local-smoke-jwt-secret-value-32-chars")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5000")
os.environ.setdefault("LOG_LEVEL", "INFO")

from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app


async def _local_user_override():
    return {"user_id": 0, "username": "local-smoke"}


def _assert_status(resp, expected: int, label: str) -> None:
    if resp.status_code != expected:
        raise AssertionError(f"{label} returned {resp.status_code}: {resp.text[:500]}")


def main() -> None:
    app.dependency_overrides[get_current_user] = _local_user_override
    message_id = f"local-smoke-{int(time.time())}"
    payload = {
        "platform": "telegram",
        "adapter": "telegram",
        "messageId": message_id,
        "conversationId": "local-smoke-chat",
        "conversationType": "private",
        "senderId": "local-user",
        "senderName": "Local User",
        "text": "local smoke hello",
        "raw": {"conversationName": "Local Smoke", "timestamp": int(time.time())},
    }

    with TestClient(app) as client:
        health = client.get("/health")
        _assert_status(health, 200, "health")
        if health.json().get("status") != "healthy":
            raise AssertionError(f"health payload is unexpected: {health.text}")

        event = client.post(
            "/api/integrations/astrbot/messages",
            headers={"X-Integration-Token": "local-verify-token"},
            json=payload,
        )
        _assert_status(event, 200, "mock AstrBot event")
        event_payload = event.json()
        for key in ("shouldReply", "replyText", "model", "costTime", "traceId"):
            if key not in event_payload:
                raise AssertionError(f"mock AstrBot event missing response field: {key}")
        if not event_payload["shouldReply"]:
            raise AssertionError(f"mock AstrBot event did not produce a reply: {event_payload}")

        history = client.get("/api/messages", params={"platform": "telegram", "limit": 5})
        _assert_status(history, 200, "history query")
        messages = history.json().get("messages", [])
        if not any(item.get("sourceMessageId") == message_id for item in messages):
            raise AssertionError("history query did not include the mock AstrBot message")

    app.dependency_overrides.clear()
    print("Local API smoke checks passed.")


if __name__ == "__main__":
    main()
