"""
Redis 客户端 — 用于缓存教务系统 Cookie 和查询结果

功能:
  1. 存储/刷新教务系统登录 Cookie (避免频繁登录)
  2. 缓存热门教室查询结果 (可选)
  3. 分布式锁 (防止多个爬虫实例同时运行)
"""
import json
from typing import Optional

import redis.asyncio as aioredis
from loguru import logger

from app.config import settings


class RedisManager:
    """Redis 连接管理器"""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("Redis 连接成功")
        return self._client

    # ─── Cookie 管理 ───

    async def save_cookies(self, key: str, cookies: dict) -> None:
        """保存教务系统 Cookie 到 Redis"""
        r = await self.get_client()
        await r.setex(
            f"cookies:{key}",
            settings.COOKIE_TTL_SECONDS,
            json.dumps(cookies),
        )
        logger.debug(f"Cookie 已保存 (key=cookies:{key}, TTL={settings.COOKIE_TTL_SECONDS}s)")

    async def load_cookies(self, key: str) -> Optional[dict]:
        """从 Redis 加载 Cookie"""
        r = await self.get_client()
        data = await r.get(f"cookies:{key}")
        if data:
            logger.debug(f"Cookie 命中缓存 (key=cookies:{key})")
            return json.loads(data)
        return None

    async def delete_cookies(self, key: str) -> None:
        """删除过期的 Cookie"""
        r = await self.get_client()
        await r.delete(f"cookies:{key}")

    # ─── 查询缓存 ───

    async def cache_query_result(self, key: str, data: list, ttl: int = 120) -> None:
        """缓存查询结果"""
        r = await self.get_client()
        await r.setex(f"query:{key}", ttl, json.dumps(data, ensure_ascii=False))

    async def get_cached_query(self, key: str) -> Optional[list]:
        """获取缓存的查询结果"""
        r = await self.get_client()
        data = await r.get(f"query:{key}")
        if data:
            return json.loads(data)
        return None

    # ─── 分布式锁 ───

    async def acquire_lock(self, lock_name: str, ttl: int = 300) -> bool:
        """获取分布式锁，防止爬虫重复运行"""
        r = await self.get_client()
        acquired = await r.setnx(f"lock:{lock_name}", "1")
        if acquired:
            await r.expire(f"lock:{lock_name}", ttl)
        return acquired

    async def release_lock(self, lock_name: str) -> None:
        """释放分布式锁"""
        r = await self.get_client()
        await r.delete(f"lock:{lock_name}")

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None


redis_manager = RedisManager()
