import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callbacks import CalendarCallback

MONTH_NAMES = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(
    year: int,
    month: int,
    busy_days: set[int],
    *,
    mode: str = "view",
    today: date | None = None,
) -> InlineKeyboardMarkup:
    today = today or date.today()
    builder = InlineKeyboardBuilder()

    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)

    builder.row(
        InlineKeyboardButton(
            text="◀️",
            callback_data=CalendarCallback(
                action="nav", year=prev_year, month=prev_month, mode=mode
            ).pack(),
        ),
        InlineKeyboardButton(
            text=f"{MONTH_NAMES[month]} {year}",
            callback_data=CalendarCallback(
                action="ignore", year=year, month=month, mode=mode
            ).pack(),
        ),
        InlineKeyboardButton(
            text="▶️",
            callback_data=CalendarCallback(
                action="nav", year=next_year, month=next_month, mode=mode
            ).pack(),
        ),
    )

    builder.row(
        *[
            InlineKeyboardButton(
                text=day,
                callback_data=CalendarCallback(
                    action="ignore", year=year, month=month, mode=mode
                ).pack(),
            )
            for day in WEEKDAYS
        ]
    )

    cal = calendar.Calendar(firstweekday=0)
    for week in cal.monthdayscalendar(year, month):
        row_buttons: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row_buttons.append(
                    InlineKeyboardButton(
                        text=" ",
                        callback_data=CalendarCallback(
                            action="ignore", year=year, month=month, mode=mode
                        ).pack(),
                    )
                )
                continue

            label = str(day)
            if day in busy_days:
                label = f"*{day}*"

            is_today = (
                today.year == year and today.month == month and today.day == day
            )
            if is_today:
                label = f"•{label}•"

            is_past_date = (
                mode in ("booking", "move")
                and (
                    year < today.year
                    or (year == today.year and month < today.month)
                    or (year == today.year and month == today.month and day < today.day)
                )
            )

            if mode == "view":
                action = "day"
            elif mode in ("booking", "move") and not is_past_date:
                action = "select"
            else:
                action = "ignore"

            if mode in ("booking", "move") and is_past_date:
                label = f"✗ {label}"

            row_buttons.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=CalendarCallback(
                        action=action, year=year, month=month, day=day, mode=mode
                    ).pack(),
                )
            )
        builder.row(*row_buttons)

    if mode in ("booking", "move"):
        builder.row(
            InlineKeyboardButton(text="❌ Отмена", callback_data="booking:cancel")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
        )

    return builder.as_markup()


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    if month < 1:
        return year - 1, 12
    if month > 12:
        return year + 1, 1
    return year, month
