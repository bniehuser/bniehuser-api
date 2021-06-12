import re
from typing import List, Dict, Optional
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ....core.messaging import SocketScope, SocketMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WebSockets')
r = None


class ConnectionManager:
    connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[client_id] = websocket

    def disconnect(self, client_id: str):
        del self.connections[client_id]

    async def send_direct_message(self, message: SocketMessage) -> bool:
        if message.recipient not in self.connections:
            return False
        await self.connections[message.recipient].send_text(message.to_str())
        return True

    async def broadcast(self, message: SocketMessage):
        for recipient in self.connections:
            if recipient != message.sender:
                await self.connections[recipient].send_text(message.to_str())


manager = ConnectionManager()
router = APIRouter()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    await manager.broadcast(SocketMessage(sender='SERVER', message=f"*{client_id}* has joined"))
    try:
        while True:
            data = await websocket.receive_text()
            msg = SocketMessage.from_str(data)
            logger.info(f"socket message: {msg.to_str()}")
            if msg.recipient:
                if not await manager.send_direct_message(msg):
                    # send an email
                    logger.warning(f"unable to send personal message to {msg.recipient}")
            else:
                await manager.broadcast(msg)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(SocketMessage(sender='SERVER', message=f"*{client_id}* has left"))

