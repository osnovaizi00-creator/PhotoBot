import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    timezone: ZoneInfo
    db_path: str = "data/photographer.db"


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN не задан в .env файле")

    raw_admins = os.getenv("ADMIN_IDS", "").strip()
    if not raw_admins:
        raise ValueError("ADMIN_IDS не задан в .env файле")

    admin_ids = frozenset(int(x.strip()) for x in raw_admins.split(",") if x.strip())

    tz_name = os.getenv("TIMEZONE", "Europe/Moscow").strip()
    try:
        timezone = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"Некорректный TIMEZONE: {tz_name}") from exc

    return Config(bot_token=token, admin_ids=admin_ids, timezone=timezone)
