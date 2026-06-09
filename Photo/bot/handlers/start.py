import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message

from bot.keyboards.main_kb import main_menu_kb

router = Router()
logger = logging.getLogger(__name__)


@router.errors()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("Ошибка при обработке обновления: %s", event.exception)


@router.message(CommandStart())
async def cmd_start(message: Message, is_admin: bool) -> None:
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Я помогу вам управлять записями на съёмки:\n"
        "• 📸 Записать новую съёмку\n"
        "• 📅 Посмотреть календарь записей\n"
        "• ⚙️ Настройки",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )
    await callback.answer()


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext, is_admin: bool) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.", reply_markup=main_menu_kb(is_admin=is_admin))
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_kb(is_admin=is_admin))
