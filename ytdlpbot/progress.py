from __future__ import annotations

import asyncio
import time
from typing import Optional

from pyrogram.types import Message


def format_bytes(value: Optional[float]) -> str:
    if value is None:
        return "unknown"

    units = ("B", "KB", "MB", "GB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024

    return f"{size:.1f}GB"


def format_eta(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"

    seconds = max(0, int(seconds))
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {remaining_minutes}m"
    if remaining_minutes:
        return f"{remaining_minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def progress_bar(current: float, total: Optional[float], width: int = 12) -> str:
    if not total:
        return "[" + "." * width + "]"

    ratio = min(max(current / total, 0), 1)
    filled = int(ratio * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


class ProgressReporter:
    def __init__(
        self,
        message: Message,
        title: str,
        *,
        interval_seconds: float = 2.0,
    ) -> None:
        self.message = message
        self.title = title
        self.interval_seconds = interval_seconds
        self.loop = asyncio.get_running_loop()
        self._last_update = 0.0
        self._last_text = ""

    async def start(self, status: str) -> None:
        await self._edit(f"**{self.title}**\n{status}")

    async def done(self, status: str) -> None:
        await self._edit(f"**{self.title}**\n{status}", force=True)

    async def fail(self, status: str) -> None:
        await self._edit(f"**{self.title}**\n{status}", force=True)

    async def update(
        self,
        status: str,
        current: float,
        total: Optional[float],
        *,
        speed: Optional[float] = None,
        eta: Optional[float] = None,
        force: bool = False,
    ) -> None:
        percent = f"{(current / total) * 100:.1f}%" if total else "unknown"
        lines = [
            f"**{self.title}**",
            status,
            f"`{progress_bar(current, total)}` {percent}",
            f"{format_bytes(current)} / {format_bytes(total)}",
        ]

        if speed:
            lines.append(f"Speed: {format_bytes(speed)}/s")
        if eta is not None:
            lines.append(f"ETA: {format_eta(eta)}")

        await self._edit("\n".join(lines), force=force)

    def sync_update(
        self,
        status: str,
        current: float,
        total: Optional[float],
        *,
        speed: Optional[float] = None,
        eta: Optional[float] = None,
        force: bool = False,
    ) -> None:
        asyncio.run_coroutine_threadsafe(
            self.update(
                status,
                current,
                total,
                speed=speed,
                eta=eta,
                force=force,
            ),
            self.loop,
        )

    async def _edit(self, text: str, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and now - self._last_update < self.interval_seconds
            and text == self._last_text
        ):
            return

        if not force and now - self._last_update < self.interval_seconds:
            return

        self._last_update = now
        self._last_text = text

        try:
            await self.message.edit(text)
        except Exception:
            pass

