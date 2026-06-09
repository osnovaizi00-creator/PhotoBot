from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database.db import Database
from bot.keyboards.calendar_kb import build_calendar
from bot.keyboards.callbacks import CalendarCallback
from bot.keyboards.main_kb import cancel_kb, main_menu_kb, skip_phone_kb
from bot.states.booking import BookingStates
router = Router()


@router.message(F.text == "📸 Записать съёмку")
async def start_booking(message: Message, state: FSMContext, db: Database) -> None:
    await state.set_state(BookingStates.date)
    today = date.today()
    busy_days = await db.get_dates_with_shoots(today.year, today.month, message.from_user.id)
    await message.answer(
        "📅 Выберите дату съёмки:",
        reply_markup=build_calendar(
            today.year, today.month, busy_days, mode="booking", today=today
        ),
    )


@router.callback_query(
    CalendarCallback.filter((F.action == "nav") & (F.mode == "booking"))
)
async def booking_calendar_nav(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext,
    db: Database,
) -> None:
    current = await state.get_state()
    if current != BookingStates.date:
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
            mode="booking",
            today=today,
        )
    )
    await callback.answer()


@router.callback_query(
    CalendarCallback.filter((F.action == "select") & (F.mode == "booking"))
)
async def booking_select_date(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext,
) -> None:
    current = await state.get_state()
    if current != BookingStates.date:
        await callback.answer()
        return

    selected = date(callback_data.year, callback_data.month, callback_data.day)
    if selected < date.today():
        await callback.answer("❌ Нельзя выбрать прошедшую дату.", show_alert=True)
        return

    await state.update_data(shoot_date=selected.isoformat())
    await state.set_state(BookingStates.time)
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Дата: <b>{selected.strftime('%d.%m.%Y')}</b>\n\n"
        "🕐 Введите время съёмки в формате <b>ЧЧ:ММ</b>\n"
        "Например: <code>14:30</code>",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "booking:cancel")
async def booking_cancel_callback(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool,
) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "Запись отменена.",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )
    await callback.answer()


@router.message(BookingStates.time)
async def booking_time(message: Message, state: FSMContext) -> None:
    if not _is_valid_time(message.text or ""):
        await message.answer(
            "❌ Неверный формат времени. Введите время как <b>ЧЧ:ММ</b>, например <code>10:00</code>",
            reply_markup=cancel_kb(),
        )
        return

    await state.update_data(shoot_time=message.text.strip())
    await state.set_state(BookingStates.name)
    await message.answer(
        "👤 Введите имя клиента:",
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.name)
async def booking_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите имя клиента:")
        return

    await state.update_data(client_name=name)
    await state.set_state(BookingStates.cost)
    await message.answer(
        "💰 Введите стоимость съёмки (число в рублях):",
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.cost)
async def booking_cost(message: Message, state: FSMContext) -> None:
    try:
        cost = float((message.text or "").replace(",", ".").replace(" ", ""))
        if cost < 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Введите корректную стоимость, например: <code>5000</code>",
            reply_markup=cancel_kb(),
        )
        return

    await state.update_data(cost=cost)
    await state.set_state(BookingStates.studio)
    await message.answer(
        "🏢 Укажите название студии или район съёмки:",
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.studio)
async def booking_studio(message: Message, state: FSMContext) -> None:
    studio_name = (message.text or "").strip()
    if len(studio_name) < 2:
        await message.answer(
            "❌ Укажите название студии или район съёмки, например: <b>Центр</b> или <b>Студия Лайт</b>",
            reply_markup=cancel_kb(),
        )
        return

    await state.update_data(studio_name=studio_name)
    await state.set_state(BookingStates.phone)
    await message.answer(
        "📞 Введите номер телефона клиента\n"
        "или нажмите <b>⏭ Пропустить</b>",
        reply_markup=skip_phone_kb(),
    )


@router.message(BookingStates.phone, F.text == "⏭ Пропустить")
async def booking_skip_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=None)
    await state.set_state(BookingStates.shoot_name)
    await message.answer(
        "🎬 Введите название съёмки (может быть любым):",
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.phone)
async def booking_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 5:
        await message.answer(
            "❌ Некорректный номер. Введите телефон или нажмите ⏭ Пропустить",
            reply_markup=skip_phone_kb(),
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(BookingStates.shoot_name)
    await message.answer(
        "🎬 Введите название съёмки (может быть любым):",
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.shoot_name)
async def booking_shoot_name(
    message: Message,
    state: FSMContext,
    db: Database,
    is_admin: bool,
) -> None:
    shoot_name = (message.text or "").strip()
    if len(shoot_name) < 1:
        await message.answer(
            "❌ Название съёмки не может быть пустым. Введите название любой съёмки:",
            reply_markup=cancel_kb(),
        )
        return

    await state.update_data(shoot_name=shoot_name)
    await _save_booking(message, state, db, is_admin)


async def _save_booking(
    message: Message,
    state: FSMContext,
    db: Database,
    is_admin: bool,
) -> None:
    data = await state.get_data()
    shoot_date = date.fromisoformat(data["shoot_date"])
    shoot_time = data["shoot_time"]
    client_name = data["client_name"]
    cost = data["cost"]
    studio_name = data.get("studio_name", "")
    shoot_name = data.get("shoot_name", "")
    phone = data.get("phone")

    shoot_id = await db.add_shoot(
        shoot_date=shoot_date,
        shoot_time=shoot_time,
        client_name=client_name,
        cost=cost,
        phone=phone,
        user_id=message.from_user.id if message.from_user else 0,
        studio_name=studio_name,
        shoot_name=shoot_name,
    )

    phone_line = f"\n📞 Телефон: {phone}" if phone else ""
    studio_line = f"\n🏢 Студия/район: <b>{studio_name}</b>" if studio_name else ""
    shoot_name_line = f"\n🎬 Название съёмки: <b>{shoot_name}</b>" if shoot_name else ""

    await state.clear()
    await message.answer(
        "✅ <b>Съёмка записана!</b>\n\n"
        f"📅 Дата: <b>{shoot_date.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Время: <b>{shoot_time}</b>\n"
        f"👤 Клиент: <b>{client_name}</b>\n"
        f"💰 Стоимость: <b>{cost:,.0f} ₽</b>"
        f"{studio_line}{shoot_name_line}{phone_line}",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


def _is_valid_time(value: str) -> bool:
    try:
        parts = value.strip().split(":")
        if len(parts) != 2:
            return False
        hour, minute = int(parts[0]), int(parts[1])
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False
