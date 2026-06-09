import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database.db import Database
from bot.utils.formatting import format_shoot

logger = logging.getLogger(__name__)


class ReminderService:
    def __init__(
        self,
        bot: Bot,
        db: Database,
        admin_ids: frozenset[int],
        timezone: ZoneInfo,
    ) -> None:
        self.bot = bot
        self.db = db
        self.admin_ids = admin_ids
        self.timezone = timezone
        self.scheduler = AsyncIOScheduler(timezone=timezone)

    def start(self) -> None:
        self.scheduler.add_job(
            self._check_reminders,
            trigger="interval",
            minutes=1,
            id="shoot_reminders",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Планировщик напоминаний запущен")

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _check_reminders(self) -> None:
        user_ids = await self.db.get_user_ids_with_shoots()
        if not user_ids:
            return

        for user_id in user_ids:
            if not await self.db.get_reminders_enabled(user_id=user_id):
                continue

            hours = await self.db.get_reminder_hours(user_id=user_id)
            timezone_name = await self.db.get_setting(
                "timezone", user_id=user_id, default=self.timezone.key
            )
            try:
                tz = ZoneInfo(timezone_name)
            except Exception:
                tz = self.timezone

            now = datetime.now(tz).replace(tzinfo=None)
            shoots = await self.db.get_upcoming_shoots_for_reminder(
                now, hours, user_id=user_id
            )

            for shoot in shoots:
                text = (
                    f"🔔 <b>Напоминание о съёмке</b>\n"
                    f"Через <b>{hours} ч.</b> у вас съёмка!\n\n"
                    f"📅 <b>{shoot.shoot_date.strftime('%d.%m.%Y')}</b>\n"
                    f"{format_shoot(shoot)}"
                )
                try:
                    await self.bot.send_message(user_id, text)
                except Exception:
                    logger.exception(
                        "Не удалось отправить напоминание user_id=%s", user_id
                    )
                await self.db.mark_reminder_sent(shoot.id)

            follow_up_shoots = await self.db.get_follow_up_shoots(
                now, user_id=user_id
            )
            for shoot in follow_up_shoots:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🗑 Удалить запись",
                                callback_data=f"shoot:confirm_delete:{shoot.id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="✅ Удалю самостоятельно позже",
                                callback_data=f"shoot:skip_followup:{shoot.id}",
                            )
                        ],
                    ]
                )
                text = (
                    "⏳ <b>Надеемся фотосессия прошла успешно!</b>\n\n"
                    "Удалить запись?"
                )
                try:
                    await self.bot.send_message(
                        user_id,
                        text,
                        reply_markup=keyboard,
                    )
                except Exception:
                    logger.exception(
                        "Не удалось отправить follow-up user_id=%s", user_id
                    )
                await self.db.mark_followup_sent(shoot.id)
