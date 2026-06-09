from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.keyboards.callbacks import AdminCallback


def main_menu_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📸 Записать съёмку"))
    builder.row(KeyboardButton(text="📅 Календарь записей"))
    builder.row(KeyboardButton(text="⚙️ Настройки"))
    if is_admin:
        builder.row(KeyboardButton(text="🛡 Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def skip_phone_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭ Пропустить"))
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def settings_panel_kb(
    reminders_enabled: bool,
    reminder_hours: int,
    timezone_name: str,
) -> InlineKeyboardMarkup:
    status = "Включены" if reminders_enabled else "Выключены"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🔔 Напоминания: {status}",
            callback_data=AdminCallback(action="toggle_reminders").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⏰ За сколько часов: {reminder_hours} ч.",
            callback_data=AdminCallback(action="set_hours").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🕒 Часовой пояс: {timezone_name}",
            callback_data=AdminCallback(action="set_timezone").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Мой заработок",
            callback_data=AdminCallback(action="earnings").pack(),
        )
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def admin_panel_kb(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data=AdminCallback(action="stats", panel="admin").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📣 Рассылка всем",
            callback_data=AdminCallback(action="broadcast", panel="admin").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🧹 Удалить все записи",
            callback_data=AdminCallback(action="clear_all", panel="admin").pack(),
        )
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def earnings_menu_kb(*, panel: str = "settings") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Месячный заработок",
            callback_data=AdminCallback(action="earnings_month", panel=panel).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Общий заработок",
            callback_data=AdminCallback(action="earnings_total", panel=panel).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=AdminCallback(action="back_to_panel", panel=panel).pack(),
        )
    )
    return builder.as_markup()
