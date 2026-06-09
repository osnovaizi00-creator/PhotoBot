from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database.db import Database
from bot.keyboards.calendar_kb import MONTH_NAMES
from bot.keyboards.callbacks import AdminCallback
from bot.keyboards.main_kb import (
    admin_panel_kb,
    earnings_menu_kb,
    main_menu_kb,
    settings_panel_kb,
)
from bot.states.booking import AdminStates

router = Router()


def _panel_is_admin(panel: str) -> bool:
    return panel == "admin"


async def _user_now(db: Database, user_id: int) -> datetime:
    tz_name = await db.get_setting("timezone", user_id=user_id, default="Europe/Moscow")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    return datetime.now(tz).replace(tzinfo=None)


@router.message(F.text == "⚙️ Настройки")
async def settings_panel(message: Message, db: Database) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await _send_panel(message, db, user_id=user_id, panel="settings")


@router.message(F.text.in_(["🛡 Админ-панель", "⚙️ Админ-панель"]))
async def admin_panel(message: Message, db: Database, is_admin: bool) -> None:
    if not is_admin:
        await message.answer("Доступ запрещён.")
        return
    user_id = message.from_user.id if message.from_user else 0
    await _send_panel(message, db, user_id=user_id, panel="admin")


@router.callback_query(AdminCallback.filter(F.action == "back_to_panel"))
async def back_to_panel(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database
) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    panel = callback_data.panel
    await callback.message.edit_text(
        await _panel_text(db, user_id, panel),
        reply_markup=await _build_panel_kb(db, user_id, panel),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "toggle_reminders"))
async def toggle_reminders(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database
) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    panel = callback_data.panel
    enabled = await db.get_reminders_enabled(user_id=user_id)
    await db.set_reminders_enabled(not enabled, user_id=user_id)
    status = "включены" if not enabled else "выключены"
    await callback.message.edit_text(
        await _panel_text(db, user_id, panel),
        reply_markup=await _build_panel_kb(db, user_id, panel),
    )
    await callback.answer(f"Напоминания {status}")


@router.callback_query(AdminCallback.filter(F.action == "set_hours"))
async def set_hours_prompt(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    await state.update_data(settings_user_id=user_id, settings_panel=callback_data.panel)
    await state.set_state(AdminStates.reminder_hours)
    await callback.message.answer(
        "⏰ Введите за сколько часов до съёмки отправлять напоминание\n"
        "(целое число, например <code>2</code>):"
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "set_timezone"))
async def set_timezone_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    await state.update_data(settings_user_id=user_id)
    tz_buttons = [
        ("Москва (Europe/Moscow)", "Europe/Moscow"),
        ("Санкт-Петербург (Europe/Saint_Petersburg)", "Europe/Saint_Petersburg"),
        ("Казань (Europe/Kazan)", "Europe/Kazan"),
        ("Екатеринбург (Asia/Yekaterinburg)", "Asia/Yekaterinburg"),
        ("Омск (Asia/Omsk)", "Asia/Omsk"),
        ("Красноярск (Asia/Krasnoyarsk)", "Asia/Krasnoyarsk"),
        ("Иркутск (Asia/Irkutsk)", "Asia/Irkutsk"),
        ("Якутск (Asia/Yakutsk)", "Asia/Yakutsk"),
        ("Владивосток (Asia/Vladivostok)", "Asia/Vladivostok"),
        ("Магадан (Asia/Magadan)", "Asia/Magadan"),
        ("Камчатка (Asia/Kamchatka)", "Asia/Kamchatka"),
    ]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"tz:{value}:settings")]
            for label, value in tz_buttons
        ]
    )
    await callback.message.answer(
        "🕒 Выберите часовой пояс для напоминаний:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"))
async def apply_timezone(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    parts = callback.data.split(":")
    tz_name = parts[1]
    panel = parts[2] if len(parts) > 2 else "settings"
    try:
        ZoneInfo(tz_name)
    except Exception:
        await callback.answer("❌ Некорректный часовой пояс.", show_alert=True)
        return

    user_id = (await state.get_data()).get("settings_user_id") or (
        callback.from_user.id if callback.from_user else 0
    )
    await db.set_setting("timezone", tz_name, user_id=user_id)
    await callback.message.edit_text(
        f"✅ Часовой пояс сохранён: <b>{tz_name}</b>",
        reply_markup=await _build_panel_kb(db, user_id, panel),
    )
    await callback.answer(f"Часовой пояс: {tz_name}")


@router.callback_query(AdminCallback.filter(F.action == "earnings"))
async def earnings_menu(callback: CallbackQuery, callback_data: AdminCallback) -> None:
    await callback.message.edit_text(
        "💰 <b>Мой заработок</b>\n\nВыберите период:",
        reply_markup=earnings_menu_kb(panel=callback_data.panel),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "earnings_month"))
async def earnings_month(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database
) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    now = await _user_now(db, user_id)
    month_key = now.strftime("%Y-%m")
    amount = await db.get_monthly_earnings(user_id, month_key)
    count = await db.get_monthly_completed_count(user_id, month_key)
    month_label = f"{MONTH_NAMES[now.month]} {now.year}"

    await callback.message.edit_text(
        f"📅 <b>Месячный заработок — {month_label}</b>\n\n"
        f"💰 Сумма: <b>{amount:,.0f} ₽</b>\n"
        f"📸 Успешных съёмок: <b>{count}</b>\n\n"
        "<i>Учитываются съёмки, удалённые после их окончания.</i>",
        reply_markup=earnings_menu_kb(panel=callback_data.panel),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "earnings_total"))
async def earnings_total(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database
) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    amount = await db.get_total_earnings(user_id)
    count = await db.get_completed_sessions_count(user_id)

    await callback.message.edit_text(
        "📊 <b>Общий заработок</b>\n\n"
        f"💰 Сумма за всё время: <b>{amount:,.0f} ₽</b>\n"
        f"📸 Успешных съёмок: <b>{count}</b>\n\n"
        "<i>Учитываются съёмки, удалённые после их окончания.</i>",
        reply_markup=earnings_menu_kb(panel=callback_data.panel),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "broadcast"))
async def broadcast_prompt(
    callback: CallbackQuery, state: FSMContext, callback_data: AdminCallback, is_admin: bool
) -> None:
    if not is_admin or callback_data.panel != "admin":
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_message)
    await callback.message.answer("📣 Введите текст рассылки для всех пользователей бота:")
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "clear_all"))
async def clear_all_prompt(callback: CallbackQuery, callback_data: AdminCallback, is_admin: bool) -> None:
    if not is_admin or callback_data.panel != "admin":
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚠️ Подтвердите удаление всех записей у всех пользователей.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, удалить всё",
                        callback_data=AdminCallback(
                            action="clear_all_execute", panel="admin"
                        ).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=AdminCallback(
                            action="cancel_clear_all", panel="admin"
                        ).pack(),
                    )
                ],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "stats"))
async def show_stats(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database, is_admin: bool
) -> None:
    if not is_admin or callback_data.panel != "admin":
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        await _stats_text(db),
        reply_markup=await _build_panel_kb(
            db, callback.from_user.id if callback.from_user else 0, "admin"
        ),
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter(F.action == "clear_all_execute"))
async def clear_all_execute(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database, is_admin: bool
) -> None:
    if not is_admin or callback_data.panel != "admin":
        await callback.answer("Нет доступа.", show_alert=True)
        return
    deleted = await db.delete_all_shoots()
    await callback.message.edit_text(
        f"🧹 Удалено всех записей: <b>{deleted}</b>",
        reply_markup=await _build_panel_kb(
            db, callback.from_user.id if callback.from_user else 0, "admin"
        ),
    )
    await callback.answer("Все записи удалены")


@router.callback_query(AdminCallback.filter(F.action == "cancel_clear_all"))
async def cancel_clear_all(
    callback: CallbackQuery, callback_data: AdminCallback, db: Database, is_admin: bool
) -> None:
    if not is_admin:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = callback.from_user.id if callback.from_user else 0
    await callback.message.edit_text(
        await _panel_text(db, user_id, "admin"),
        reply_markup=await _build_panel_kb(db, user_id, "admin"),
    )
    await callback.answer("Отмена")


@router.message(AdminStates.broadcast_message)
async def broadcast_message(message: Message, state: FSMContext, db: Database, bot) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Введите текст для рассылки.")
        return

    user_ids = await db.get_user_ids_with_shoots()
    sent = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            pass

    await db.record_broadcast(sent)
    await state.clear()
    await message.answer(
        f"✅ Рассылка отправлена <b>{sent}</b> пользователю(ям).",
        reply_markup=main_menu_kb(is_admin=True),
    )


@router.message(AdminStates.reminder_hours)
async def set_hours_value(
    message: Message, state: FSMContext, db: Database, is_admin: bool
) -> None:
    try:
        hours = int((message.text or "").strip())
        if hours < 1 or hours > 72:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 72")
        return

    data = await state.get_data()
    user_id = data.get("settings_user_id") or (message.from_user.id if message.from_user else 0)
    panel = data.get("settings_panel", "settings")
    await db.set_reminder_hours(hours, user_id=user_id)
    await state.clear()
    await message.answer(
        f"✅ Напоминания будут приходить за <b>{hours}</b> ч. до съёмки",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )
    await _send_panel(message, db, user_id=user_id, panel=panel)


@router.message(AdminStates.timezone)
async def set_timezone_value(
    message: Message, state: FSMContext, db: Database, is_admin: bool
) -> None:
    tz_name = (message.text or "").strip() or "Europe/Moscow"
    try:
        ZoneInfo(tz_name)
    except Exception:
        await message.answer("❌ Некорректный часовой пояс. Пример: <code>Europe/Moscow</code>")
        return

    data = await state.get_data()
    user_id = data.get("settings_user_id") or (message.from_user.id if message.from_user else 0)
    panel = data.get("settings_panel", "settings")
    await db.set_setting("timezone", tz_name, user_id=user_id)
    await state.clear()
    await message.answer(
        f"✅ Часовой пояс сохранён: <b>{tz_name}</b>",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )
    await _send_panel(message, db, user_id=user_id, panel=panel)


async def _send_panel(
    message: Message, db: Database, user_id: int, panel: str
) -> None:
    await message.answer(
        await _panel_text(db, user_id, panel),
        reply_markup=await _build_panel_kb(db, user_id, panel),
    )


async def _stats_text(db: Database) -> str:
    active_users = await db.get_active_user_count()
    active_records = await db.get_active_shoot_count()
    broadcasts_total = await db.get_broadcast_count_total()
    broadcasts_today = await db.get_broadcast_count_today()
    return (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей бота: <b>{active_users}</b>\n"
        f"📣 Рассылок всего: <b>{broadcasts_total}</b>\n"
        f"📅 Рассылок сегодня: <b>{broadcasts_today}</b>\n"
        f"🗂 Активных записей: <b>{active_records}</b>"
    )


async def _panel_text(db: Database, user_id: int, panel: str) -> str:
    enabled = await db.get_reminders_enabled(user_id=user_id)
    hours = await db.get_reminder_hours(user_id=user_id)
    timezone_name = await db.get_setting("timezone", user_id=user_id, default="Europe/Moscow")
    status = "включены ✅" if enabled else "выключены ❌"
    title = "🛡 <b>Админ-панель</b>" if _panel_is_admin(panel) else "⚙️ <b>Настройки</b>"
    return (
        f"{title}\n\n"
        f"🔔 Напоминания: <b>{status}</b>\n"
        f"⏰ За сколько часов: <b>{hours} ч.</b>\n"
        f"🕒 Часовой пояс: <b>{timezone_name}</b>\n\n"
        "Используйте кнопки ниже для настройки."
    )


async def _build_panel_kb(db: Database, user_id: int, panel: str):
    if _panel_is_admin(panel):
        return admin_panel_kb(is_admin=True)

    return settings_panel_kb(
        reminders_enabled=await db.get_reminders_enabled(user_id=user_id),
        reminder_hours=await db.get_reminder_hours(user_id=user_id),
        timezone_name=await db.get_setting("timezone", user_id=user_id, default="Europe/Moscow"),
    )
