"""
QuantFree 券商网关（macOS + evolving）
实现 QuantFree 约定的 5 个 REST 接口，内部调用 [evolving](https://github.com/zetatez/evolving) 控制同花顺 Mac 版。
仅支持 macOS；需先安装并配置 evolving（同花顺 2.3.1、cliclick、~/.config/evolving/config.xml）。
邮件：QQ/163/Gmail 等在 broker_gateway/mail_sender.py 中走 465/SSL，不修改 evolving 子模块。
evolving_repo 与远程完全一致；财通证券(CTZQ)等通过 ascmds_adapter 在运行时注入。
"""
import asyncio
import os
import sys
from datetime import datetime
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException

from config import EVOLVING_PATH, GATEWAY_PORT
from schemas import OrderCreate, Order, Position, AccountInfo

app = FastAPI(title="QuantFree Broker Gateway (macOS + evolving)", version="0.2.0")

def _ensure_darwin():
    if sys.platform != "darwin":
        raise HTTPException(status_code=503, detail="本网关仅支持 macOS（evolving）。")

if EVOLVING_PATH:
    sys.path.insert(0, EVOLVING_PATH)
else:
    _gateway_dir = os.path.dirname(os.path.abspath(__file__))
    _evolving_repo = os.path.join(_gateway_dir, "evolving_repo")
    if os.path.isdir(_evolving_repo):
        sys.path.insert(0, _evolving_repo)

# ---------------------------------------------------------------------------
# evolving 调用（同步，在线程池执行）
# ---------------------------------------------------------------------------

_evolving_instance: Any = None


def _get_evolving():
    global _evolving_instance
    if _evolving_instance is None:
        try:
            from mail_sender import install_mail_adapter
            install_mail_adapter()  # QQ/163/Gmail 等 465/SSL 发信，不修改 evolving 子模块
            from ascmds_adapter import install_broker_adapter
            install_broker_adapter()  # 财通等券商在运行时注入，不修改 evolving 子模块
            from evolving.evolving import Evolving
            _evolving_instance = Evolving()
            _evolving_instance.keepInformed = True
        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail=f"未找到 evolving：请配置 EVOLVING_PATH 或执行 git submodule update --init。{e}",
            )
    return _evolving_instance


async def _run_evolving_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------
# 响应构造（QuantFree 契约）
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().isoformat()


def _order_dict(
    order_id: str,
    stock_code: str,
    stock_name: str,
    order_type: str,
    side: str,
    quantity: int,
    status: str = "PENDING",
    filled_quantity: int = 0,
    filled_price: float = 0.0,
    price: Optional[float] = None,
) -> dict:
    return {
        "id": order_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "type": side,
        "order_type": order_type,
        "price": price,
        "quantity": quantity,
        "status": status,
        "filled_quantity": filled_quantity,
        "filled_price": filled_price,
        "stamp_tax": 0.0,
        "commission": 0.0,
        "transfer_fee": 0.0,
        "total_fee": 0.0,
        "slippage": 0.0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _account_from_evolving(data: dict) -> dict:
    # evolving getAccountInfo 的 data: 可用金额, 总资产, 总市值, 总盈亏, 资金余额 等
    def g(key: str, default=0.0):
        v = data.get(key)
        if v is None:
            return default
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return default

    return {
        "total_asset": g("总资产"),
        "available_cash": g("可用金额", g("资金余额")),
        "market_value": g("总市值"),
        "profit": g("总盈亏"),
        "profit_percent": g("总盈亏", 0.0) / g("总资产", 1.0) * 100 if g("总资产") else 0.0,
        "total_fees_paid": 0.0,
    }


def _position_from_evolving_row(comment: List[str], row: List[str]) -> dict:
    d = dict(zip(comment, row)) if comment and row else {}
    def g(k: str, default=0.0):
        v = d.get(k)
        if v is None:
            return default
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return default
    def gi(k: str, default=0):
        v = d.get(k)
        if v is None:
            return default
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return default
    return {
        "stock_code": d.get("证券代码", ""),
        "stock_name": d.get("证券名称", ""),
        "quantity": gi("实际数量", gi("股票余额")),
        "cost_price": g("成本价"),
        "current_price": g("市价"),
        "market_value": g("市值"),
        "profit": g("盈亏"),
        "profit_percent": g("浮动盈亏比(%)"),
        "total_fees": 0.0,
        "realized_profit": 0.0,
    }


def _order_from_entrust_row(comment: List[str], row: List[str]) -> Optional[dict]:
    d = dict(zip(comment, row)) if comment and row else {}
    opr = d.get("操作", "")
    side = "BUY" if "买" in opr or opr == "buy" else "SELL"
    qty = int(float(str(d.get("委托数量", 0)).replace(",", ""))) if d.get("委托数量") else 0
    price_s = d.get("委托价格") or d.get("成交价格") or "0"
    try:
        price_f = float(str(price_s).replace(",", ""))
    except (ValueError, TypeError):
        price_f = 0.0
    filled_price = float(str(d.get("成交价格", price_s)).replace(",", "")) if d.get("成交价格") else price_f
    contract_no = (d.get("合同编号") or "").strip()
    if not contract_no:
        contract_no = f"entrust-{hash(str(row)) % 10**10}"
    return _order_dict(
        order_id=contract_no,
        stock_code=d.get("证券代码", ""),
        stock_name=d.get("证券名称", ""),
        order_type="LIMIT",
        side=side,
        quantity=qty,
        status="PENDING",
        filled_quantity=0,
        filled_price=filled_price,
        price=price_f or None,
    )


# ---------------------------------------------------------------------------
# 5 个路由（QuantFree 约定）
# ---------------------------------------------------------------------------

@app.post("/order", response_model=Order)
async def place_order(order: OrderCreate):
    """下单：通过 evolving 委托同花顺 Mac 版。"""
    _ensure_darwin()
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    ev = _get_evolving()
    price_arg = order.price if order.order_type == "LIMIT" and order.price is not None else None
    if order.type == "BUY":
        status, contract_no = await _run_evolving_sync(ev.buy, order.stock_code, order.quantity, price_arg)
    else:
        status, contract_no = await _run_evolving_sync(ev.sell, order.stock_code, order.quantity, price_arg)
    if not status:
        raise HTTPException(status_code=400, detail=contract_no or "委托失败")
    order_id = contract_no or ""
    resp = _order_dict(
        order_id=order_id,
        stock_code=order.stock_code,
        stock_name=order.stock_name or f"股票{order.stock_code}",
        order_type=order.order_type,
        side=order.type,
        quantity=order.quantity,
        status="PENDING",
        filled_quantity=0,
        filled_price=price_arg or 0.0,
        price=order.price,
    )
    return Order(**resp)


@app.get("/orders")
async def get_orders(status: Optional[str] = None) -> List[Order]:
    """当日委托列表（合并 stock / sciTech / gem）。"""
    _ensure_darwin()
    ev = _get_evolving()
    all_entrust: List[dict] = []
    for asset in ("stock", "sciTech", "gem"):
        try:
            res = await _run_evolving_sync(ev.getEntrust, asset, "today", False)
        except Exception:
            continue
        if not res.get("status") or not res.get("data"):
            continue
        comment = res.get("comment") or []
        for row in res.get("data") or []:
            o = _order_from_entrust_row(comment, row)
            if o and (status is None or o.get("status") == status):
                all_entrust.append(Order(**o))
    return all_entrust


@app.get("/positions")
async def get_positions() -> List[Position]:
    """持仓列表（合并 A 股 / 科创板 / 创业板）。"""
    _ensure_darwin()
    ev = _get_evolving()
    all_holding = await _run_evolving_sync(ev.getAllHoldingShares)
    positions: List[Position] = []
    for _key, res in (all_holding or {}).items():
        if not isinstance(res, dict) or not res.get("status") or not res.get("data"):
            continue
        comment = res.get("comment") or []
        for row in res.get("data") or []:
            p = _position_from_evolving_row(comment, row)
            if p.get("quantity", 0) > 0:
                positions.append(Position(**p))
    return positions


@app.get("/account")
async def get_account() -> AccountInfo:
    """账户资金。"""
    _ensure_darwin()
    ev = _get_evolving()
    res = await _run_evolving_sync(ev.getAccountInfo)
    if not res.get("status"):
        raise HTTPException(status_code=502, detail=res.get("info", "获取账户失败"))
    data = res.get("data") or {}
    return AccountInfo(**_account_from_evolving(data))


@app.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    """撤单：按合同编号撤销（先试 stock，再试 sciTech/gem）。"""
    _ensure_darwin()
    if not order_id or not order_id.strip():
        raise HTTPException(status_code=400, detail="order_id 不能为空")
    ev = _get_evolving()
    for asset in ("stock", "sciTech", "gem"):
        ok = await _run_evolving_sync(ev.revokeContractNoEntrust, asset, order_id.strip())
        if ok:
            return {"success": True, "data": True}
    raise HTTPException(status_code=400, detail="撤单失败或合同编号不存在")


@app.get("/health")
async def health():
    return {"status": "ok", "platform": sys.platform, "backend": "evolving"}
