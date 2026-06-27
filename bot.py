import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import settings
from db.database import create_pool, close_pool
from middlewares.db import DbMiddleware
from middlewares.auth import AuthMiddleware
from utils.logger import logger

from handlers import (
    super_admin, admin, worker,
    admin_worker, super_mini_admin_worker, user, start
)


async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.update.middleware(DbMiddleware())
    dp.update.middleware(AuthMiddleware())

    # Routers
    # bot.py
    dp.include_router(start.router)  # ← birinchi
    dp.include_router(super_mini_admin_worker.router)  # ← birinchi
    dp.include_router(super_admin.router)
    dp.include_router(admin.router)
    dp.include_router(worker.router)
    dp.include_router(admin_worker.router)
    dp.include_router(user.router)                     # ← oxirgi

    # DB ulanish
    await create_pool()
    logger.info("🚀 Bot ishga tushdi")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await close_pool()
        await bot.session.close()
        logger.info("🛑 Bot to'xtatildi")


if __name__ == "__main__":
    asyncio.run(main())