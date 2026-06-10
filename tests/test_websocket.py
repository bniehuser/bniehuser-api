from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


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
