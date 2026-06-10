import hashlib
import hmac
import re
import time
from enum import Enum
from typing import Annotated

import httpx
import structlog
from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from app.core.config import settings

log = structlog.get_logger()
router = APIRouter()

REPLAY_WINDOW_SECONDS = 300
HUB_BOT_URL = "http://hub-bot:9000/send"


class SocketScope(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    SYSTEM = "system"


class SocketSource(str, Enum):
    SERVER = "server"
    CLIENT = "client"
    BOT = "bot"


class SocketMessage(BaseModel):
    scope: SocketScope = SocketScope.PUBLIC
    source: SocketSource = SocketSource.SERVER
    type: str | None = None
    sender: str | None = None
    recipient: str | None = None
    message: str


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections[client_id] = ws

    def disconnect(self, client_id: str) -> None:
        self.connections.pop(client_id, None)

    async def send_direct(self, recipient: str, msg: SocketMessage) -> bool:
        ws = self.connections.get(recipient)
        if ws is None:
            return False
        await ws.send_text(msg.model_dump_json())
        return True

    async def broadcast(self, msg: SocketMessage) -> None:
        for ws in list(self.connections.values()):
            await ws.send_text(msg.model_dump_json())


manager = ConnectionManager()


def _build_origin_re() -> re.Pattern[str]:
    allowed = [str(o).rstrip("/") for o in settings.BACKEND_CORS_ORIGINS]
    parts: list[str] = []
    if allowed:
        parts.append("|".join(re.escape(o) for o in allowed))
    if settings.BACKEND_CORS_ORIGIN_REGEX:
        parts.append(settings.BACKEND_CORS_ORIGIN_REGEX)
    if not parts:
        return re.compile(r"(?!)")
    return re.compile("|".join(f"(?:{p})" for p in parts))


_ORIGIN_RE = _build_origin_re()


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    return _ORIGIN_RE.match(origin.rstrip("/")) is not None


@router.websocket("/ws/{client_id}")
async def ws_endpoint(websocket: WebSocket, client_id: str) -> None:
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        return
    await manager.connect(client_id, websocket)
    await manager.broadcast(SocketMessage(sender="SERVER", message=f"*{client_id}* has joined"))
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = SocketMessage.model_validate_json(data)
            except ValueError:
                log.warning("ws_bad_payload", client_id=client_id)
                continue
            if msg.recipient:
                ok = await manager.send_direct(msg.recipient, msg)
                if not ok:
                    log.warning("ws_unknown_recipient", recipient=msg.recipient)
            elif msg.scope == SocketScope.PRIVATE and msg.sender:
                await manager.send_direct(msg.sender, msg)
            else:
                await manager.broadcast(msg)
                if msg.scope == SocketScope.PUBLIC and msg.source != SocketSource.BOT:
                    await discord_outbound(
                        SocketScope.PUBLIC, msg.message, sender=msg.sender or "web"
                    )
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(SocketMessage(sender="SERVER", message=f"*{client_id}* has left"))


class IncomingDiscordPayload(BaseModel):
    scope: SocketScope
    sender: str
    message: str


def _verify_signature(*, timestamp: str, body: bytes, signature: str) -> bool:
    expected_hex = hmac.new(
        settings.FORWARD_HMAC_SECRET.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected_hex}", signature)


@router.post("/internal/discord/incoming")
async def incoming_discord(
    request: Request,
    x_forward_timestamp: Annotated[str | None, Header(alias="X-Forward-Timestamp")] = None,
    x_forward_signature: Annotated[str | None, Header(alias="X-Forward-Signature")] = None,
) -> dict[str, str]:
    if x_forward_timestamp is None or x_forward_signature is None:
        raise HTTPException(status_code=400, detail="Missing forwarding headers")
    try:
        ts = int(x_forward_timestamp)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Bad timestamp") from err
    if abs(int(time.time()) - ts) > REPLAY_WINDOW_SECONDS:
        raise HTTPException(status_code=400, detail="Stale timestamp")
    body = await request.body()
    if not _verify_signature(
        timestamp=x_forward_timestamp, body=body, signature=x_forward_signature
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        data = IncomingDiscordPayload.model_validate_json(body)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Bad payload") from err
    msg = SocketMessage(
        scope=data.scope,
        source=SocketSource.BOT,
        sender=data.sender,
        message=data.message,
    )
    if msg.scope == SocketScope.PUBLIC:
        await manager.broadcast(msg)
    return {"status": "ok"}


async def discord_outbound(scope: SocketScope, message: str, sender: str = "web") -> None:
    payload = {"scope": scope.value, "sender": sender, "message": message}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                HUB_BOT_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.BOT_API_TOKEN}"},
            )
    except httpx.HTTPError as err:
        log.warning("discord_outbound_failed", error=str(err))
