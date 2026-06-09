from aiogram import Router

from bot.handlers import admin, booking, calendar_view, start


def setup_routers(admin_ids: frozenset[int]) -> Router:
    from bot.filters.admin import IsAdmin

    admin_filter = IsAdmin(admin_ids)
    root = Router()
    root.include_router(start.router)

    for module in (booking, calendar_view, admin):
        module.router.message.filter(admin_filter)
        module.router.callback_query.filter(admin_filter)
        root.include_router(module.router)

    return root
