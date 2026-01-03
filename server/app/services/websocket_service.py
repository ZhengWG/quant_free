"""
WebSocket服务
"""

from fastapi import WebSocket
from loguru import logger
from typing import Dict, Set


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str = "default"):
        """连接WebSocket"""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        """断开WebSocket连接"""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        logger.info(f"WebSocket disconnected from channel: {channel}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict, channel: str = "default"):
        """广播消息"""
        if channel in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    disconnected.add(connection)
            
            # 清理断开的连接
            for conn in disconnected:
                self.active_connections[channel].discard(conn)


manager = ConnectionManager()


def setup_websocket(app):
    """设置WebSocket路由"""
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                # 处理消息
                if data.get("type") == "subscribe":
                    # 订阅行情数据
                    logger.info(f"Subscribe to: {data.get('data')}")
                elif data.get("type") == "unsubscribe":
                    # 取消订阅
                    logger.info(f"Unsubscribe from: {data.get('data')}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            manager.disconnect(websocket)

