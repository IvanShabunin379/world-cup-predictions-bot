import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, predict, standings, upcoming, history, admin, rules
from services.notifications import start_scheduler

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(predict.router)
    dp.include_router(standings.router)
    dp.include_router(upcoming.router)
    dp.include_router(history.router)
    dp.include_router(admin.router)
    dp.include_router(rules.router)

    start_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
