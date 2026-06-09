from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import httpx
from aiogram.__meta__ import __version__
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import InputFile

if TYPE_CHECKING:
    from aiogram.client.bot import Bot


def _to_form_value(value: Any) -> str | int | float:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    return str(value)


class HttpxSession(BaseSession):
    """HTTP-сессия на httpx — стабильнее aiohttp на Windows с VPN."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=30.0),
                headers={"User-Agent": f"aiogram/{__version__} httpx"},
                follow_redirects=True,
            )
        return self._client

    def build_form_data(
        self, bot: Bot, method: TelegramMethod[TelegramType]
    ) -> tuple[dict[str, Any], dict[str, tuple[str, bytes]]]:
        data: dict[str, Any] = {}
        raw_files: dict[str, InputFile] = {}

        for key, value in method.model_dump(warnings=False).items():
            prepared = self.prepare_value(value, bot=bot, files=raw_files)
            if not prepared:
                continue
            data[key] = _to_form_value(prepared)

        files: dict[str, tuple[str, bytes]] = {}
        for key, value in raw_files.items():
            files[key] = (value.filename or key, value.read(bot))

        return data, files

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        client = await self._get_client()
        url = self.api.api_url(token=bot.token, method=method.__api_method__)
        data, files = self.build_form_data(bot, method)

        try:
            response = await client.post(
                url,
                data=data,
                files=files or None,
                timeout=timeout or self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise TelegramNetworkError(
                method=method, message="Request timeout error"
            ) from exc
        except httpx.HTTPError as exc:
            raise TelegramNetworkError(
                method=method, message=f"{type(exc).__name__}: {exc}"
            ) from exc

        result = self.check_response(
            bot=bot,
            method=method,
            status_code=response.status_code,
            content=response.text,
        )
        return cast(TelegramType, result.result)

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        client = await self._get_client()
        try:
            async with client.stream(
                "GET",
                url,
                headers=headers or {},
                timeout=timeout,
            ) as response:
                if raise_for_status:
                    response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size):
                    yield chunk
        except httpx.HTTPError as exc:
            raise TelegramNetworkError(method=None, message=str(exc)) from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
