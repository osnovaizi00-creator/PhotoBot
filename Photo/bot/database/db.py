from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass
class Shoot:
    id: int
    shoot_date: date
    shoot_time: str
    client_name: str
    cost: float
    phone: str | None
    user_id: int
    studio_name: str
    shoot_name: str
    reminder_sent: bool
    followup_sent: bool
    created_at: datetime


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS shoots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shoot_date TEXT NOT NULL,
                    shoot_time TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    cost REAL NOT NULL,
                    phone TEXT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    studio_name TEXT NOT NULL DEFAULT '',
                    shoot_name TEXT NOT NULL DEFAULT '',
                    reminder_sent INTEGER NOT NULL DEFAULT 0,
                    followup_sent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            pragma_cursor = await db.execute("PRAGMA table_info(shoots)")
            existing_columns = {row[1] for row in await pragma_cursor.fetchall()}
            if "user_id" not in existing_columns:
                await db.execute(
                    "ALTER TABLE shoots ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
                )
            if "studio_name" not in existing_columns:
                await db.execute(
                    "ALTER TABLE shoots ADD COLUMN studio_name TEXT NOT NULL DEFAULT ''"
                )
            if "shoot_name" not in existing_columns:
                await db.execute(
                    "ALTER TABLE shoots ADD COLUMN shoot_name TEXT NOT NULL DEFAULT ''"
                )
            if "followup_sent" not in existing_columns:
                await db.execute(
                    "ALTER TABLE shoots ADD COLUMN followup_sent INTEGER NOT NULL DEFAULT 0"
                )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS earnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    shoot_id INTEGER NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    deleted_at TEXT NOT NULL,
                    month_key TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS broadcast_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_at TEXT NOT NULL,
                    recipients INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('reminders_enabled', '1')
                """
            )
            await db.execute(
                """
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('reminder_hours', '2')
                """
            )
            await db.commit()

    async def add_shoot(
        self,
        shoot_date: date,
        shoot_time: str,
        client_name: str,
        cost: float,
        phone: str | None,
        user_id: int,
        studio_name: str = "",
        shoot_name: str = "",
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO shoots (
                    shoot_date,
                    shoot_time,
                    client_name,
                    cost,
                    phone,
                    user_id,
                    studio_name,
                    shoot_name,
                    followup_sent,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shoot_date.isoformat(),
                    shoot_time,
                    client_name,
                    cost,
                    phone,
                    user_id,
                    studio_name,
                    shoot_name,
                    0,
                    datetime.now().isoformat(),
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_shoot_by_id(self, shoot_id: int) -> Shoot | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM shoots WHERE id = ?",
                (shoot_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_shoot(row) if row else None

    async def update_shoot_date(self, shoot_id: int, shoot_date: date) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shoots SET shoot_date = ? WHERE id = ?",
                (shoot_date.isoformat(), shoot_id),
            )
            await db.commit()

    async def update_shoot_time(self, shoot_id: int, shoot_time: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shoots SET shoot_time = ? WHERE id = ?",
                (shoot_time.strip(), shoot_id),
            )
            await db.commit()

    async def delete_shoot(self, shoot_id: int, *, deleted_at: datetime | None = None) -> Shoot | None:
        shoot = await self.get_shoot_by_id(shoot_id)
        if shoot is None:
            return None

        if deleted_at is not None:
            shoot_dt = self._combine_datetime(shoot.shoot_date, shoot.shoot_time)
            if shoot_dt is not None and deleted_at >= shoot_dt:
                await self.record_completed_shoot(
                    user_id=shoot.user_id,
                    shoot_id=shoot.id,
                    amount=shoot.cost,
                    deleted_at=deleted_at,
                    shoot_date=shoot.shoot_date,
                )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM shoots WHERE id = ?", (shoot_id,))
            await db.commit()
        return shoot

    async def delete_shoot_simple(self, shoot_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM shoots WHERE id = ?", (shoot_id,))
            await db.commit()

    async def delete_all_shoots(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM shoots")
            await db.commit()
            return cursor.rowcount or 0

    async def get_shoots_by_date(self, shoot_date: date, user_id: int) -> list[Shoot]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM shoots
                WHERE shoot_date = ? AND user_id = ?
                ORDER BY shoot_time
                """,
                (shoot_date.isoformat(), user_id),
            )
            rows = await cursor.fetchall()
            return [self._row_to_shoot(row) for row in rows]

    async def get_dates_with_shoots(self, year: int, month: int, user_id: int) -> set[int]:
        prefix = f"{year:04d}-{month:02d}-"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT DISTINCT shoot_date FROM shoots
                WHERE shoot_date LIKE ? AND user_id = ?
                """,
                (f"{prefix}%", user_id),
            )
            rows = await cursor.fetchall()
            days: set[int] = set()
            for (shoot_date_str,) in rows:
                day = int(shoot_date_str.split("-")[2])
                days.add(day)
            return days

    async def get_upcoming_shoots_for_reminder(
        self, now: datetime, hours_before: int, user_id: int | None = None
    ) -> list[Shoot]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM shoots
                WHERE reminder_sent = 0 AND (? IS NULL OR user_id = ?)
                """,
                (user_id, user_id),
            )
            rows = await cursor.fetchall()
            shoots = [self._row_to_shoot(row) for row in rows]
            result: list[Shoot] = []
            for shoot in shoots:
                shoot_dt = self._combine_datetime(shoot.shoot_date, shoot.shoot_time)
                if shoot_dt is None:
                    continue
                delta = shoot_dt - now
                total_seconds = delta.total_seconds()
                if 0 < total_seconds <= hours_before * 3600:
                    result.append(shoot)
            return result

    async def mark_reminder_sent(self, shoot_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shoots SET reminder_sent = 1 WHERE id = ?",
                (shoot_id,),
            )
            await db.commit()

    async def mark_followup_sent(self, shoot_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shoots SET followup_sent = 1 WHERE id = ?",
                (shoot_id,),
            )
            await db.commit()

    async def get_setting(
        self, key: str, default: str = "", user_id: int | None = None
    ) -> str:
        setting_key = self._setting_key(key, user_id)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (setting_key,),
            )
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(
        self, key: str, value: str, user_id: int | None = None
    ) -> None:
        setting_key = self._setting_key(key, user_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (setting_key, value),
            )
            await db.commit()

    async def get_reminders_enabled(self, user_id: int | None = None) -> bool:
        return (await self.get_setting("reminders_enabled", "1", user_id=user_id)) == "1"

    async def set_reminders_enabled(self, enabled: bool, user_id: int | None = None) -> None:
        await self.set_setting("reminders_enabled", "1" if enabled else "0", user_id=user_id)

    async def get_reminder_hours(self, user_id: int | None = None) -> int:
        raw = await self.get_setting("reminder_hours", "2", user_id=user_id)
        try:
            return max(1, int(raw))
        except ValueError:
            return 2

    async def set_reminder_hours(self, hours: int, user_id: int | None = None) -> None:
        await self.set_setting("reminder_hours", str(max(1, hours)), user_id=user_id)

    async def get_user_ids_with_shoots(self) -> list[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT user_id FROM shoots WHERE user_id > 0"
            )
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def record_completed_shoot(
        self,
        user_id: int,
        shoot_id: int,
        amount: float,
        deleted_at: datetime,
        shoot_date: date,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM earnings WHERE shoot_id = ? AND user_id = ?",
                (shoot_id, user_id),
            )
            if await cursor.fetchone():
                return
            await db.execute(
                """
                INSERT INTO earnings (user_id, shoot_id, amount, deleted_at, month_key, completed)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    user_id,
                    shoot_id,
                    amount,
                    deleted_at.isoformat(),
                    shoot_date.strftime("%Y-%m"),
                ),
            )
            await db.commit()

    async def get_monthly_earnings(self, user_id: int, month_key: str | None = None) -> float:
        month_key = month_key or datetime.now().strftime("%Y-%m")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM earnings WHERE user_id = ? AND month_key = ?",
                (user_id, month_key),
            )
            row = await cursor.fetchone()
            return float(row[0] or 0)

    async def get_monthly_completed_count(
        self, user_id: int, month_key: str | None = None
    ) -> int:
        month_key = month_key or datetime.now().strftime("%Y-%m")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM earnings WHERE user_id = ? AND month_key = ?",
                (user_id, month_key),
            )
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def get_total_earnings(self, user_id: int) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM earnings WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return float(row[0] or 0)

    async def get_completed_sessions_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM earnings WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def get_global_earning_stats(self) -> tuple[int, float]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM earnings")
            row = await cursor.fetchone()
            return int(row[0] or 0), float(row[1] or 0)

    async def reset_earnings_stats(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM earnings")
            await db.commit()
            return int(cursor.rowcount or 0)

    async def get_active_user_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM shoots WHERE user_id > 0"
            )
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def get_active_shoot_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM shoots")
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def record_broadcast(self, recipients: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO broadcast_stats (sent_at, recipients) VALUES (?, ?)",
                (datetime.now().isoformat(), recipients),
            )
            await db.commit()

    async def get_broadcast_count_total(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM broadcast_stats")
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def get_broadcast_count_today(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM broadcast_stats WHERE date(sent_at) = date('now')"
            )
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def get_follow_up_shoots(
        self, now: datetime, user_id: int | None = None
    ) -> list[Shoot]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id is None:
                cursor = await db.execute(
                    """
                    SELECT * FROM shoots
                    WHERE followup_sent = 0
                      AND datetime(shoot_date || ' ' || shoot_time, '+1 hour') <= ?
                    """,
                    (now.strftime("%Y-%m-%d %H:%M:%S"),),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM shoots
                    WHERE followup_sent = 0
                      AND user_id = ?
                      AND datetime(shoot_date || ' ' || shoot_time, '+1 hour') <= ?
                    """,
                    (user_id, now.strftime("%Y-%m-%d %H:%M:%S")),
                )
            rows = await cursor.fetchall()
            return [self._row_to_shoot(row) for row in rows]

    @staticmethod
    def _setting_key(key: str, user_id: int | None) -> str:
        return f"user:{user_id}:{key}" if user_id is not None else key

    @staticmethod
    def _row_to_shoot(row: aiosqlite.Row) -> Shoot:
        has_studio = "studio_name" in row.keys()
        has_shoot_name = "shoot_name" in row.keys()

        return Shoot(
            id=row["id"],
            shoot_date=date.fromisoformat(row["shoot_date"]),
            shoot_time=row["shoot_time"],
            client_name=row["client_name"],
            cost=row["cost"],
            phone=row["phone"],
            user_id=int(row["user_id"]) if "user_id" in row.keys() else 0,
            studio_name=row["studio_name"] if has_studio else "",
            shoot_name=row["shoot_name"] if has_shoot_name else "",
            reminder_sent=bool(row["reminder_sent"]),
            followup_sent=bool(row["followup_sent"]) if "followup_sent" in row.keys() else False,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _combine_datetime(shoot_date: date, shoot_time: str) -> datetime | None:
        try:
            parts = shoot_time.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return datetime(
                shoot_date.year, shoot_date.month, shoot_date.day, hour, minute
            )
        except (ValueError, IndexError):
            return None
