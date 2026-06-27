import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("carpet_bot")
logger.setLevel(logging.DEBUG)

# Konsol
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
))

# Fayl (max 5MB, 3 ta backup)
file_handler = RotatingFileHandler(
    "logs/bot.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

logger.addHandler(console)
logger.addHandler(file_handler)


async def log_action(
    tg_id: int,
    action: str,
    details: str = None,
    workshop_id: int = None,
    is_error: bool = False
):
    """DB ga log yozish"""
    try:
        from db.database import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bot_logs (tg_id, workshop_id, action, details, is_error)
                VALUES ($1, $2, $3, $4, $5)
                """,
                tg_id, workshop_id, action, details, is_error
            )
    except Exception as e:
        logger.error(f"Log yozishda xatolik: {e}")

    if is_error:
        logger.error(f"[{tg_id}] {action}: {details}")
    else:
        logger.info(f"[{tg_id}] {action}: {details or ''}")