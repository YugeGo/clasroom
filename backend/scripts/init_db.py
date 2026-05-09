"""
数据库初始化脚本

用法:
    python -m scripts.init_db          # 创建所有表
    python -m scripts.init_db --drop   # 先删后建（开发环境重置用）

通过 SQLAlchemy ORM 的 Base.metadata.create_all() 创建所有表，
包括 sdufe_free_rooms 以及原有的 buildings/rooms/schedules 等。
"""
import argparse
import asyncio
import sys
import os

# 将项目根目录加入 sys.path，确保可以 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from loguru import logger

from app.database.session import engine, Base
from app.database import models  # noqa: F401 — 注册所有模型到 Base.metadata


async def init_db(drop_first: bool = False):
    """初始化数据库：创建（或重建）所有表"""
    if drop_first:
        logger.warning("⚠️  删除所有现有表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("所有表已删除")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 验证表已创建
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = [row[0] for row in result]
        logger.info(f"✅ 数据库初始化完成，当前表: {tables}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="山财空教室狙击手 — 数据库初始化")
    parser.add_argument("--drop", action="store_true", help="先删除所有表再重建")
    args = parser.parse_args()

    asyncio.run(init_db(drop_first=args.drop))


if __name__ == "__main__":
    main()
