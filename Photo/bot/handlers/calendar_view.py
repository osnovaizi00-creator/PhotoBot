from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database.db import Database
from bot.keyboards.calendar_kb import build_calendar, MONTH_NAMES
from bot.keyboards.callbacks import CalendarCallback
from bot.keyboards.main_kb import main_menu_kb
from bot.states.booking import BookingStates
from bot.utils.formatting import format_shoot, format_shoots_list

router = Router()


@router.message(F.text == "📅 Календарь записей")
async def show_calendar(message: Message, db: Database) -> None:
    today = date.today()
    user_id = message.from_user.id if message.from_user else 0
    busy_days = await db.get_dates_with_shoots(today.year, today.month, user_id)
    await message.answer(
        "📅 <b>Календарь записей</b>\n\n"
        "Дни со съёмками выделены звёздочками\n"
        "Нажмите на день, чтобы увидеть детали.",
        reply_markup=build_calendar(
            today.year, today.month, busy_days, mode="view", today=today
        ),
    )


@router.callback_query(
    CalendarCallback.filter((F.action == "nav") & (F.mode == "view"))
)
async def calendar_nav(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    db: Database,
) -> None:
    busy_days = await db.get_dates_with_shoots(
        callback_data.year, callback_data.month, callback.from_user.id
    )
    today = date.today()
    await callback.message.edit_text(
        "📅 <b>Календарь записей</b>\n\n"
        "Дни со съёмками выделены звёздочками\n"
        "Нажмите на день, чтобы увидеть детали.",
        reply_markup=build_calendar(
            callback_data.year,
            callback_data.month,
            busy_days,
            mode="view",
            today=today,
        ),
    )
    await callback.answer()


@router.callback_query(
    CalendarCallback.filter((F.action == "day") & (F.mode == "view"))
)
async def calendar_day_details(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    db: Database,
) -> None:
    selected = date(callback_data.year, callback_data.month, callback_data.day)
    shoots = await db.get_shoots_by_date(selected, callback.from_user.id)
    title = (
        f"📅 <b>{selected.day} {MONTH_NAMES[selected.month]} {selected.year}</b>"
    )
    text = format_shoots_list(shoots, title)

    today = date.today()
    busy_days = await db.get_dates_with_shoots(
        callback_data.year, callback_data.month, callback.from_user.id
    )

    action_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        f"🔁 Перенести {shoot.client_name.strip() or shoot.shoot_name.strip() or f'#{shoot.id}'}"
                    ),
                    callback_data=f"shoot:move:{shoot.id}",
                ),
                InlineKeyboardButton(
                    text=(
                        f"🗑 Удалить {shoot.client_name.strip() or shoot.shoot_name.strip() or f'#{shoot.id}'}"
                    ),
                    callback_data=f"shoot:delete:{shoot.id}",
                ),
            ]
            for shoot in shoots
        ]
    )
    calendar_markup = build_calendar(
        callback_data.year,
        callback_data.month,
        busy_days,
        mode="view",
        today=today,
    )
    action_markup.inline_keyboard.extend(calendar_markup.inline_keyboard)

    await callback.message.edit_text(
        text,
        reply_markup=action_markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shoot:move:"))
async def start_move_shoot(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    shoot_id = int(callback.data.split(":")[-1])
    shoot = await db.get_shoot_by_id(shoot_id)
    if shoot is None:
        await callback.answer("Съёмка не найдена.", show_alert=True)
        return
    if shoot.user_id != (callback.from_user.id if callback.from_user else 0):
        await callback.answer("Эта запись не принадлежит вам.", show_alert=True)
        return

    await state.set_state(BookingStates.move_date)
    await state.update_data(move_shoot_id=shoot_id)

    today = date.today()
    busy_days = await db.get_dates_with_shoots(
        today.year,
        today.month,
        callback.from_user.id,
    )
    await callback.message.edit_text(
        f"📅 Выберите новую дату для съёмки #{shoot_id}.\n"
        "Нажмите на день в календаре, чтобы перенести запись.",
        reply_markup=build_calendar(
            today.year,
            today.month,
            busy_days,
            mode="move",
            today=today,
        ),
    )
    await callback.answer("Выберите новую дату")


@router.callback_query(
    CalendarCallback.filter((F.action == "nav") & (F.mode == "move"))
)
async def move_calendar_nav(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext,
    db: Database,
) -> None:
    current = await state.get_state()
    if current != BookingStates.move_date:
        await callback.answer()
        return

    busy_days = await db.get_dates_with_shoots(
        callback_data.year, callback_data.month, callback.from_user.id
    )
    today = date.today()
    await callback.message.edit_reply_markup(
        reply_markup=build_calendar(
            callback_data.year,
            callback_data.month,
            busy_days,
            mode="move",
            today=today,
        )
    )
    await callback.answer()


@router.callback_query(
    CalendarCallback.filter((F.action == "select") & (F.mode == "move"))
)
async def move_select_date(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext,
    db: Database,
) -> None:
    current = await state.get_state()
    if current != BookingStates.move_date:
        await callback.answer()
        return

    data = await state.get_data()
    shoot_id = data.get("move_shoot_id")
    if not shoot_id:
        await callback.answer("Съёмка не выбрана.", show_alert=True)
        return

    shoot = await db.get_shoot_by_id(int(shoot_id))
    if shoot is None or shoot.user_id != (callback.from_user.id if callback.from_user else 0):
        await callback.answer("Эта запись не принадлежит вам.", show_alert=True)
        return

    selected = date(callback_data.year, callback_data.month, callback_data.day)
    if selected < date.today():
        await callback.answer("❌ Нельзя выбрать прошедшую дату.", show_alert=True)
        return

    await state.update_data(move_date=selected.isoformat())
    await state.set_state(BookingStates.move_time)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"📅 Дата выбрана: <b>{selected.strftime('%d.%m.%Y')}</b>\n"
        "⏰ Теперь введите новое время съёмки в формате <code>HH:MM</code>, например <code>14:30</code>.",
        reply_markup=main_menu_kb(is_admin=(callback.from_user.id if callback.from_user else 0) in {int(x) for x in __import__('os').getenv('ADMIN_IDS', '').split(',') if x.strip()}),
    )
    await callback.answer(
        f"Дата выбрана: {selected.strftime('%d.%m.%Y')}. Введите время.",
        show_alert=True,
    )


@router.message(BookingStates.move_time)
async def move_shoot_time(message: Message, state: FSMContext, db: Database) -> None:
    text = (message.text or "").strip()
    try:
        parts = text.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        new_time = f"{hour:02d}:{minute:02d}"
    except (ValueError, IndexError):
        await message.answer(
            "❌ Введите время в формате <code>HH:MM</code>, например <code>14:30</code>."
        )
        return

    data = await state.get_data()
    shoot_id = data.get("move_shoot_id")
    move_date = data.get("move_date")
    if not shoot_id or not move_date:
        await message.answer("⚠️ Не удалось определить запись для переноса.")
        return

    shoot = await db.get_shoot_by_id(int(shoot_id))
    if shoot is None or shoot.user_id != (message.from_user.id if message.from_user else 0):
        await message.answer("Эта запись не принадлежит вам.")
        await state.clear()
        return

    selected = date.fromisoformat(move_date)
    await db.update_shoot_date(int(shoot_id), selected)
    await db.update_shoot_time(int(shoot_id), new_time)
    await state.clear()

    title = shoot.shoot_name.strip() or shoot.client_name.strip() or f"Съёмка #{shoot_id}"
    await message.answer(
        f"✅ {title}, запись перенесена на <b>{selected.strftime('%d.%m.%Y')}</b> в <b>{new_time}</b>.",
        reply_markup=main_menu_kb(is_admin=(message.from_user.id if message.from_user else 0) in {int(x) for x in __import__('os').getenv('ADMIN_IDS', '').split(',') if x.strip()}),
    )


@router.callback_query(F.data.startswith("shoot:delete:"))
async def request_delete_shoot(callback: CallbackQuery, db: Database) -> None:
    shoot_id = int(callback.data.split(":")[-1])
    shoot = await db.get_shoot_by_id(shoot_id)
    if shoot is None:
        await callback.answer("Съёмка не найдена.", show_alert=True)
        return
    if shoot.user_id != (callback.from_user.id if callback.from_user else 0):
        await callback.answer("Эта запись не принадлежит вам.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 Подтвердите удаление съёмки #{shoot_id}?\n\n"
        f"{format_shoot(shoot)}\n\n"
        "Выберите действие ниже.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, удалить",
                        callback_data=f"shoot:confirm_delete:{shoot_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="shoot:cancel_delete",
                    )
                ],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shoot:skip_followup:"))
async def skip_followup(callback: CallbackQuery, db: Database) -> None:
    shoot_id = int(callback.data.split(":")[-1])
    await db.mark_followup_sent(shoot_id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Напоминание закрыто.")


@router.callback_query(F.data == "shoot:cancel_delete")
async def cancel_delete_shoot(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Удаление отменено.",
        reply_markup=main_menu_kb(is_admin=(callback.from_user.id if callback.from_user else 0) in {int(x) for x in __import__('os').getenv('ADMIN_IDS', '').split(',') if x.strip()}),
    )
    await callback.answer("Удаление отменено")


@router.callback_query(F.data.startswith("shoot:confirm_delete:"))
async def confirm_delete_shoot(callback: CallbackQuery, db: Database) -> None:
    shoot_id = int(callback.data.split(":")[-1])
    shoot = await db.get_shoot_by_id(shoot_id)

    if shoot is None:
        await callback.answer("Съёмка не найдена.", show_alert=True)
        return

    if shoot.user_id != (callback.from_user.id if callback.from_user else 0):
        await callback.answer("Эта запись не принадлежит вам.", show_alert=True)
        return

    title = shoot.shoot_name.strip() or shoot.client_name.strip() or f"Съёмка #{shoot_id}"

    tz_name = await db.get_setting(
        "timezone", user_id=shoot.user_id, default="Europe/Moscow"
    )
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    now = datetime.now(tz).replace(tzinfo=None)
    shoot_dt = db._combine_datetime(shoot.shoot_date, shoot.shoot_time)
    counted = shoot_dt is not None and now >= shoot_dt

    await db.delete_shoot(shoot_id, deleted_at=now)

    extra = ""
    if counted:
        extra = f"\n\n💰 <b>{shoot.cost:,.0f} ₽</b> добавлено к заработку."

    await callback.message.edit_text(f"🗑 <b>{title}</b>, запись удалена.{extra}")
    await callback.answer(f"{title}, запись удалена.", show_alert=True)


@router.callback_query(CalendarCallback.filter(F.action == "ignore"))
async def calendar_ignore(callback: CallbackQuery) -> None:
    await callback.answer()
