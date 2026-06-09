from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from bot.database.db import Database


def _get_user(event: TelegramObject) -> User | None:
    if isinstance(event, (Message, CallbackQuery)):
        return event.from_user
    return getattr(event, "from_user", None)


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db
        return await handler(event, data)


class AdminMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: frozenset[int]) -> None:
        self.admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = _get_user(event) or data.get("event_from_user")
        data["is_admin"] = user is not None and user.id in self.admin_ids
        return await handler(event, data)
