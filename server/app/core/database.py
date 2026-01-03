"""
数据库初始化
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from loguru import logger
from app.core.config import settings

# 确保数据目录存在
os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)

# 创建异步引擎（SQLite使用aiosqlite）
database_url = f"sqlite+aiosqlite:///{settings.DB_PATH}"
engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    future=True
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def init_db():
    """初始化数据库"""
    from app.models import stock, strategy, order, position, market_cache
    
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def get_db():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

