"""
服务入口文件
"""

import os
import sys
import subprocess
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import market, strategy, trade, backtest
from app.services.websocket_service import setup_websocket

# 券商网关默认端口（与 broker_gateway 一致）
BROKER_GATEWAY_PORT = 7070


def _broker_gateway_url_is_local() -> bool:
    url = (settings.BROKER_API_URL or "").strip().rstrip("/")
    return (
        f"127.0.0.1:{BROKER_GATEWAY_PORT}" in url
        or f"localhost:{BROKER_GATEWAY_PORT}" in url
    )


def _start_broker_gateway_process():
    """启动 broker_gateway（evolving）子进程，返回 Popen 或 None。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gw_dir = os.path.join(root, "broker_gateway")
    if not os.path.isdir(gw_dir) or not os.path.isfile(os.path.join(gw_dir, "main.py")):
        logger.warning("broker_gateway 目录不存在或缺少 main.py，跳过自动启动")
        return None
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(BROKER_GATEWAY_PORT),
            ],
            cwd=gw_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env={**os.environ},
        )
        logger.info(f"已自动启动券商网关 (evolving)，pid={proc.pid}，端口 {BROKER_GATEWAY_PORT}")
        return proc
    except Exception as e:
        logger.warning(f"自动启动券商网关失败: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting QuantFree Server...")
    await init_db()
    logger.info("Database initialized")

    app.state.broker_gateway_process = None
    if (
        settings.TRADING_MODE == "live"
        and getattr(settings, "AUTO_START_BROKER_GATEWAY", False)
        and _broker_gateway_url_is_local()
    ):
        proc = _start_broker_gateway_process()
        if proc is not None:
            app.state.broker_gateway_process = proc
            await asyncio.sleep(1.5)

    yield

    # 关闭时执行
    if getattr(app.state, "broker_gateway_process", None) is not None:
        try:
            app.state.broker_gateway_process.terminate()
            app.state.broker_gateway_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"关闭券商网关进程时出错: {e}")
        app.state.broker_gateway_process = None
    logger.info("Shutting down QuantFree Server...")


# 创建FastAPI应用
app = FastAPI(
    title="QuantFree API",
    description="VSCode股票交易助手后端服务",
    version="0.1.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "QuantFree",
        "version": "0.1.0"
    }


# 注册路由
app.include_router(market.router, prefix="/api/v1/market", tags=["行情数据"])
app.include_router(strategy.router, prefix="/api/v1/strategy", tags=["策略推荐"])
app.include_router(trade.router, prefix="/api/v1/trade", tags=["交易执行"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["策略回测"])

# 设置WebSocket
setup_websocket(app)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "error": str(exc) if settings.DEBUG else None
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

