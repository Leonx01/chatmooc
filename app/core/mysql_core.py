import contextlib
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 构造异步连接字符串
ASYNC_SQLALCHEMY_URI = f"mysql+asyncmy://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""

    pass


class DatabaseManager:
    def __init__(self, host: str, engine_kwargs: dict = None):
        # 1. 创建异步引擎
        self.engine: AsyncEngine = create_async_engine(
            host,
            **engine_kwargs
            or {
                "pool_size": 10,  # 连接池基础大小
                "max_overflow": 20,  # 允许超过 pool_size 的最大连接数
                "pool_pre_ping": True,  # 每次借出连接时先探活，避免使用失效连接
                "pool_recycle": 1800,  # 连接回收时间（秒）
                "echo": True,  # 生产环境建议 False，设为 True 可看 SQL 日志
            },
        )

        # 2. 创建异步 Session 工厂
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @contextlib.asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        提供一个异步 Session 上下文管理器。
        确保在执行完毕后自动关闭 Session，并在发生异常时回滚。
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """关闭引擎，释放连接池"""
        await self.engine.dispose()


# 初始化全局实例
db_manager = DatabaseManager(ASYNC_SQLALCHEMY_URI)
