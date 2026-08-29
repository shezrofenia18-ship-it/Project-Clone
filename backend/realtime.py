"""Realtime push (WebSocket) untuk Berkah Ayam Mili.

Desain sengaja dibuat sederhana & tahan gagal:
- Server TIDAK mengirim data bisnis lewat socket, hanya sinyal "topik ini berubah".
  Frontend yang menerima sinyal langsung refetch endpoint REST yang sudah ada.
  Keuntungannya: tidak ada duplikasi logika, payload kecil, dan otorisasi tetap
  dipegang endpoint REST (kasir tidak bisa "menguping" data owner).
- Semua broadcast bersifat best-effort: kalau socket mati/putus, transaksi
  penjualan TIDAK BOLEH gagal. Karena itu `emit()` menelan semua exception.
- Frontend tetap punya polling sebagai jaring pengaman.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

import jwt
from fastapi import WebSocket, WebSocketDisconnect

from auth import JWT_ALGORITHM, get_jwt_secret

logger = logging.getLogger("berkah.realtime")

# Detik menunggu pesan dari klien sebelum server mengirim heartbeat.
HEARTBEAT_SECONDS = 25


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: Set[WebSocket] = set()
        self._meta: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket, user: Dict[str, Any]) -> None:
        async with self._lock:
            self._conns.add(ws)
            self._meta[id(ws)] = user

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.discard(ws)
            self._meta.pop(id(ws), None)

    async def snapshot(self) -> List[WebSocket]:
        async with self._lock:
            return list(self._conns)

    @property
    def count(self) -> int:
        return len(self._conns)

    async def clients(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._meta.values())

    async def broadcast(self, event: Dict[str, Any]) -> int:
        targets = await self.snapshot()
        if not targets:
            return 0
        text = json.dumps(event)
        dead: List[WebSocket] = []
        sent = 0
        for ws in targets:
            try:
                await ws.send_text(text)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.remove(ws)
        return sent


manager = ConnectionManager()


async def emit(topics: Iterable[str] | str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Kirim sinyal perubahan. Tidak pernah melempar exception."""
    try:
        if isinstance(topics, str):
            topics = [topics]
        event = {
            "type": "invalidate",
            "topics": list(topics),
            "payload": payload or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast(event)
    except Exception as e:  # pragma: no cover - realtime tidak boleh menjatuhkan request
        logger.warning("Broadcast realtime gagal (diabaikan): %s", e)


def _decode(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    payload: Optional[Dict[str, Any]] = None
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if not payload or not payload.get("sub") or payload.get("type") != "access":
        return None
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


async def ws_handler(websocket: WebSocket) -> None:
    """Handler /api/ws?token=<jwt>.

    Token dikirim via query string karena browser WebSocket API tidak mendukung
    custom header. Token yang sama dengan REST (JWT Bearer), diverifikasi di sini.
    """
    user = _decode(websocket.query_params.get("token"))
    if not user:
        # 1008 = policy violation. Frontend akan berhenti mencoba & pakai polling.
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await manager.add(websocket, user)
    try:
        await websocket.send_text(json.dumps({
            "type": "hello",
            "role": user.get("role"),
            "clients": manager.count,
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_SECONDS)
                if msg == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Heartbeat supaya proxy/ingress tidak menutup koneksi idle.
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.info("WebSocket ditutup: %s", e)
    finally:
        await manager.remove(websocket)
