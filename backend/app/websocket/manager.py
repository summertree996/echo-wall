from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._users: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, wall_id: str, websocket: WebSocket, user: dict[str, Any], subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self._rooms[wall_id].add(websocket)
        self._users[websocket] = user

    def disconnect(self, wall_id: str, websocket: WebSocket) -> None:
        self._rooms[wall_id].discard(websocket)
        self._users.pop(websocket, None)
        if not self._rooms[wall_id]:
            self._rooms.pop(wall_id, None)

    async def broadcast(self, wall_id: str, event: dict[str, Any], exclude: WebSocket | None = None) -> None:
        stale: list[WebSocket] = []
        for connection in list(self._rooms.get(wall_id, set())):
            if exclude is not None and connection is exclude:
                continue
            try:
                await connection.send_json(event)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self._rooms[wall_id].discard(connection)
            self._users.pop(connection, None)

    def online_users(self, wall_id: str) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ws in self._rooms.get(wall_id, set()):
            user = self._users.get(ws)
            user_id = user.get("id") if user else None
            if not user_id or user_id in seen:
                continue
            seen.add(user_id)
            users.append(user)
        return users

    def has_user(self, wall_id: str, user_id: str) -> bool:
        return any(
            self._users.get(ws, {}).get("id") == user_id
            for ws in self._rooms.get(wall_id, set())
        )


manager = ConnectionManager()
