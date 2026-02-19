"""
本地测试：不依赖 evolving 与同花顺，通过 mock 验证网关路由与响应格式。
使用 unittest；非 macOS 下需 mock sys.platform 为 darwin。
"""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app


class TestGateway(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["backend"], "evolving")

    def test_place_order_success(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = (True, "N123456")
            r = self.client.post(
                "/order",
                json={
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "type": "BUY",
                    "order_type": "MARKET",
                    "quantity": 100,
                },
            )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["stock_code"], "000001")
        self.assertEqual(data["stock_name"], "平安银行")
        self.assertEqual(data["type"], "BUY")
        self.assertEqual(data["quantity"], 100)
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["id"], "N123456")
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_place_order_validation(self):
        r = self.client.post(
                "/order",
                json={
                    "stock_code": "000001",
                    "type": "BUY",
                    "order_type": "MARKET",
                    "quantity": 0,
                },
            )
        self.assertIn(r.status_code, (400, 422, 503))

    def test_place_order_evolving_fail(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = (False, "余额不足")
            r = self.client.post(
                "/order",
                json={"stock_code": "000001", "type": "BUY", "order_type": "MARKET", "quantity": 100},
            )
        self.assertEqual(r.status_code, 400)
        self.assertIn("余额不足", r.json().get("detail", ""))

    def test_get_orders(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = {
                "status": True,
                "comment": ["委托日期", "委托时间", "证券代码", "证券名称", "操作", "委托数量", "委托价格", "成交价格", "合同编号", "委托属性"],
                "data": [["20240101", "09:30", "000001", "平安银行", "买入", "200", "10.50", "10.52", "N888", "限价"]],
            }
            r = self.client.get("/orders")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        if data:
            o = data[0]
            self.assertEqual(o["stock_code"], "000001")
            self.assertIn(o["id"], ("N888", "entrust-"))

    def test_get_orders_empty(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = {"status": True, "data": [], "comment": []}
            r = self.client.get("/orders")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_get_positions(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = {
                "stock": {
                    "status": True,
                    "comment": ["证券代码", "证券名称", "市价", "盈亏", "浮动盈亏比(%)", "实际数量", "股票余额", "可用余额", "冻结数量", "成本价", "市值", "交易市场", "股东账户"],
                    "data": [["600519", "贵州茅台", "1520", "2000", "1.33", "100", "100", "100", "0", "1500", "152000", "上海Ａ股", "A123"]],
                },
                "sciTech": {"status": True, "data": [], "comment": []},
                "gem": {"status": True, "data": [], "comment": []},
            }
            r = self.client.get("/positions")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        if data:
            p = data[0]
            self.assertEqual(p["stock_code"], "600519")
            self.assertEqual(p["quantity"], 100)
            self.assertEqual(p["cost_price"], 1500.0)
            self.assertEqual(p["current_price"], 1520.0)

    def test_get_account(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = {
                "status": True,
                "data": {"总资产": "500000", "可用金额": "300000", "总市值": "200000", "总盈亏": "5000"},
            }
            r = self.client.get("/account")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total_asset", data)
        self.assertIn("available_cash", data)
        self.assertEqual(data["available_cash"], 300000.0)

    def test_cancel_order_success(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = True
            r = self.client.delete("/order/N123456")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("success") or data is True)

    def test_cancel_order_fail(self):
        with patch("main._ensure_darwin"), patch("main._get_evolving"), patch("main._run_evolving_sync", new_callable=AsyncMock) as m:
            m.return_value = False
            r = self.client.delete("/order/bad-id")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
