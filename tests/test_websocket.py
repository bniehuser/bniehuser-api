import hashlib
import hmac
import json

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app

_INCOMING = "/api/v1/internal/discord/incoming"
_DEV_ORIGIN = {"origin": "http://localhost:5173"}


def _bot_sign(payload: dict) -> tuple[bytes, str]:
    """Replicate discord-bot/bot/forwards.py: compact JSON, body-only HMAC."""
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = "sha256=" + hmac.new(
        settings.FORWARD_HMAC_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return body, sig


def test_ws_rejects_missing_origin() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/api/v1/ws/test"):
                raise AssertionError("expected reject")
        except WebSocketDisconnect as exc:
            assert exc.code == 1008


def test_ws_rejects_disallowed_origin() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect(
                "/api/v1/ws/test", headers={"origin": "https://evil.example.com"}
            ):
                raise AssertionError("expected reject")
        except WebSocketDisconnect as exc:
            assert exc.code == 1008


def test_ws_accepts_dev_origin() -> None:
    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/ws/dev", headers={"origin": "http://localhost:5173"}
        ) as ws:
            # First broadcast is the "X has joined" server message.
            data = ws.receive_text()
            assert "dev" in data
            assert "joined" in data


def test_incoming_discord_rejects_bad_signature() -> None:
    body, _ = _bot_sign({"scope": "PUBLIC", "sender": "gort", "message": "hi"})
    with TestClient(app) as client:
        resp = client.post(
            _INCOMING,
            content=body,
            headers={"Content-Type": "application/json", "X-Bot-Signature": "sha256=bad"},
        )
        assert resp.status_code == 401


def test_incoming_discord_broadcasts_to_ws_client() -> None:
    # Bot fans out an UPPERCASE scope, body-only X-Bot-Signature, no timestamp.
    payload = {"scope": "PUBLIC", "sender": "gort", "message": "hello from discord"}
    body, sig = _bot_sign(payload)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/web", headers=_DEV_ORIGIN) as ws:
            ws.receive_text()  # drain the "*web* has joined" broadcast
            resp = client.post(
                _INCOMING,
                content=body,
                headers={"Content-Type": "application/json", "X-Bot-Signature": sig},
            )
            assert resp.status_code == 200
            relayed = json.loads(ws.receive_text())
            assert relayed["message"] == "hello from discord"
            assert relayed["sender"] == "gort"
            assert relayed["source"] == "bot"
