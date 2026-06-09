import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.client.httpx_session import HttpxSession
from bot.config import load_config
from bot.database.db import Database
from bot.handlers import setup_routers
from bot.middlewares.deps import AdminMiddleware, DatabaseMiddleware
from bot.scheduler.reminders import ReminderService
from bot.utils.single_instance import BotAlreadyRunningError, ensure_single_instance


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    db = Database(config.db_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        session=HttpxSession(),
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DatabaseMiddleware(db))
    dp.update.middleware(AdminMiddleware(config.admin_ids))
    dp.include_router(setup_routers(config.admin_ids))

    reminders = ReminderService(
        bot=bot,
        db=db,
        admin_ids=config.admin_ids,
        timezone=config.timezone,
    )
    reminders.start()

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        reminders.stop()
        await bot.session.close()


def _run() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        ensure_single_instance()
    except BotAlreadyRunningError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    asyncio.run(main())


if __name__ == "__main__":
    _run()
