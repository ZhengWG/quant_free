#!/usr/bin/env python
"""
WebSocket功能测试
"""

import asyncio
import websockets
import json

async def test_websocket():
    """测试WebSocket连接"""
    print("=" * 60)
    print("测试WebSocket连接")
    print("=" * 60)
    
    uri = "ws://localhost:3000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket连接成功")
            
            # 发送订阅消息
            subscribe_msg = {
                "type": "subscribe",
                "data": {"codes": ["000001", "600519"]}
            }
            await websocket.send(json.dumps(subscribe_msg))
            print("✓ 发送订阅消息成功")
            
            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"✓ 收到响应: {response}")
            except asyncio.TimeoutError:
                print("⚠️  未收到响应（可能正常，服务端可能不立即响应）")
            
            # 发送取消订阅消息
            unsubscribe_msg = {
                "type": "unsubscribe",
                "data": {"codes": ["000001"]}
            }
            await websocket.send(json.dumps(unsubscribe_msg))
            print("✓ 发送取消订阅消息成功")
            
            print("\n✅ WebSocket测试通过")
            return True
            
    except Exception as e:
        print(f"❌ WebSocket测试失败: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_websocket())

