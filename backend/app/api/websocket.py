from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set
import json
import asyncio
from datetime import datetime

from app.core.telegram_auth import verify_telegram_init_data
from app.config import get_settings

router = APIRouter(prefix="", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections by telegram user ID"""
    
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        print(f"User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"User {user_id} disconnected. Remaining: {len(self.active_connections.get(user_id, set()))}")
    
    async def send_personal_message(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            dead_connections = set()
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead_connections.add(ws)
            
            # Clean up dead connections
            for ws in dead_connections:
                self.disconnect(ws, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast to all connected users"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(user_id, message)


manager = ConnectionManager()


@router.websocket("/ws/updates")
async def websocket_endpoint(
    websocket: WebSocket,
    init_data: str = Query(..., alias="initData")
):
    """WebSocket endpoint for real-time updates"""
    settings = get_settings()
    
    # Verify initData
    try:
        verified = await verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
        user_id = verified["user"]["id"]
    except Exception as e:
        await websocket.close(code=4003, reason="Invalid initData")
        return
    
    await manager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "WELCOME",
            "data": {"message": "Connected to Aegis Quant real-time updates"},
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive
        while True:
            # Wait for ping or timeout
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "PONG", "timestamp": datetime.utcnow().isoformat()})
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "KEEPALIVE", "timestamp": datetime.utcnow().isoformat()})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_id)


# Functions for engines to send updates
async def send_position_update(user_id: int, position: dict):
    await manager.send_personal_message(user_id, {
        "type": "POSITION_UPDATE",
        "data": position,
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_pnl_tick(user_id: int, portfolio_value: float, daily_pnl: float):
    await manager.send_personal_message(user_id, {
        "type": "PNL_TICK",
        "data": {"portfolioValue": portfolio_value, "dailyPnL": daily_pnl},
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_new_signal(user_id: int, signal: dict):
    await manager.send_personal_message(user_id, {
        "type": "NEW_SIGNAL",
        "data": signal,
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_trade_filled(user_id: int, trade: dict):
    await manager.send_personal_message(user_id, {
        "type": "TRADE_FILLED",
        "data": trade,
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_agent_status(user_id: int, active: bool, target: str):
    await manager.send_personal_message(user_id, {
        "type": "AGENT_STATUS",
        "data": {"active": active, "target": target},
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_risk_alert(user_id: int, rule: str, triggered: bool):
    await manager.send_personal_message(user_id, {
        "type": "RISK_ALERT",
        "data": {"rule": rule, "triggered": triggered},
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_whitelist_changed(user_id: int, added: list, removed: list):
    await manager.send_personal_message(user_id, {
        "type": "WHITELIST_CHANGED",
        "data": {"added": added, "removed": removed},
        "timestamp": datetime.utcnow().isoformat()
    })