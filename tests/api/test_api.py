#!/usr/bin/env python
"""
API功能测试脚本
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:3000"

async def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("1. 测试健康检查接口")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def test_market_realtime():
    """测试实时行情接口"""
    print("\n" + "=" * 60)
    print("2. 测试实时行情接口")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/market/realtime",
                params={"codes": "000001,600519"}
            )
            print(f"状态码: {response.status_code}")
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get("success") and data.get("data"):
                print(f"✓ 成功获取 {len(data['data'])} 只股票数据")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def test_strategy_generate():
    """测试策略生成接口"""
    print("\n" + "=" * 60)
    print("3. 测试策略生成接口")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "stock_code": "000001",
                "risk_level": "MEDIUM",
                "time_horizon": "短期"
            }
            response = await client.post(
                f"{BASE_URL}/api/v1/strategy/generate",
                json=payload
            )
            print(f"状态码: {response.status_code}")
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get("success") and data.get("data"):
                strategy = data["data"]
                print(f"✓ 策略生成成功")
                print(f"  - 股票: {strategy.get('stock_name')} ({strategy.get('stock_code')})")
                print(f"  - 建议: {strategy.get('action')}")
                print(f"  - 置信度: {strategy.get('confidence', 0) * 100:.1f}%")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            return False

async def test_trade_orders():
    """测试订单查询接口"""
    print("\n" + "=" * 60)
    print("4. 测试订单查询接口")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/v1/trade/orders")
            print(f"状态码: {response.status_code}")
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get("success"):
                print(f"✓ 成功查询订单列表")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def test_trade_positions():
    """测试持仓查询接口"""
    print("\n" + "=" * 60)
    print("5. 测试持仓查询接口")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/v1/trade/positions")
            print(f"状态码: {response.status_code}")
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get("success"):
                print(f"✓ 成功查询持仓列表")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def test_trade_account():
    """测试账户信息接口"""
    print("\n" + "=" * 60)
    print("6. 测试账户信息接口")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/v1/trade/account")
            print(f"状态码: {response.status_code}")
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get("success"):
                print(f"✓ 成功查询账户信息")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def test_api_docs():
    """测试API文档访问"""
    print("\n" + "=" * 60)
    print("7. 测试API文档访问")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/docs")
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"✓ API文档可访问: {BASE_URL}/docs")
                return True
            return False
        except Exception as e:
            print(f"❌ 错误: {e}")
            return False

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 QuantFree API 功能测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试地址: {BASE_URL}\n")
    
    # 等待服务启动
    print("等待服务启动...")
    await asyncio.sleep(2)
    
    results = []
    
    # 运行测试
    results.append(("健康检查", await test_health()))
    results.append(("实时行情", await test_market_realtime()))
    results.append(("策略生成", await test_strategy_generate()))
    results.append(("订单查询", await test_trade_orders()))
    results.append(("持仓查询", await test_trade_positions()))
    results.append(("账户信息", await test_trade_account()))
    results.append(("API文档", await test_api_docs()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("=" * 60 + "\n")
    
    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查服务日志")

if __name__ == "__main__":
    asyncio.run(main())

