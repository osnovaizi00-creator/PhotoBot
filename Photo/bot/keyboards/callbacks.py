from aiogram.filters.callback_data import CallbackData


class CalendarCallback(CallbackData, prefix="cal"):
    action: str
    year: int
    month: int
    day: int = 0
    mode: str = "view"


class AdminCallback(CallbackData, prefix="adm"):
    action: str
    panel: str = "settings"
