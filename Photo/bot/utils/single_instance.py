from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO

_lock_handle: TextIO | None = None


class BotAlreadyRunningError(RuntimeError):
    pass


def ensure_single_instance(lock_path: str = "data/bot.lock") -> None:
    global _lock_handle

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        _lock_handle = _acquire_windows(path)
        return

    _lock_handle = _acquire_unix(path)


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (OSError, ValueError):
        return None


def _acquire_windows(path: Path) -> TextIO:
    import msvcrt

    handle = open(path, "a+", encoding="utf-8")
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        stale_pid = _read_lock_pid(path)
        if stale_pid and not _pid_is_running(stale_pid):
            path.unlink(missing_ok=True)
            return _acquire_windows(path)
        raise BotAlreadyRunningError(
            "Бот уже запущен. Остановите другой экземпляр (Ctrl+C в терминале) "
            "и запустите снова."
        ) from exc

    handle.seek(0)
    handle.truncate()

    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _acquire_unix(path: Path) -> TextIO:
    import fcntl

    handle = open(path, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise BotAlreadyRunningError(
            "Бот уже запущен. Остановите другой экземпляр и запустите снова."
        ) from exc

    handle.write(str(os.getpid()))
    handle.flush()
    return handle
