"""
服务入口文件
"""

import os
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting QuantFree Server...")
    await init_db()
    logger.info("Database initialized")
    yield
    # 关闭时执行
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

