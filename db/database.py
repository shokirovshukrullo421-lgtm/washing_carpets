import asyncpg
from config import settings
from utils.logger import logger


pool: asyncpg.Pool | None = None


async def create_pool():
    global pool
    pool = await asyncpg.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        min_size=2,
        max_size=10
    )
    logger.info("✅ DB pool yaratildi")


async def close_pool():
    global pool
    if pool:
        await pool.close()
        logger.info("🛑 DB pool yopildi")


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("DB pool yaratilmagan")
    return pool