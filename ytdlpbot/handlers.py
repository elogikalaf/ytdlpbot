from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ytdlpbot.auth import (
    reject_callback_if_unauthorized,
    reject_message_if_unauthorized,
)
from ytdlpbot.cache import VideoCache, VideoEntry
from ytdlpbot.config import Settings
from ytdlpbot.media import VIDEO_EXTENSIONS, download_media, extract_info, make_video_id
from ytdlpbot.progress import ProgressReporter, format_bytes


def _format_size(size: Any) -> str:
    return format_bytes(size) if size else "unknown size"


def _title(info: Dict[str, Any]) -> str:
    return str(info.get("title") or "Untitled")[:60]


def _download_progress_hook(reporter: ProgressReporter):
    def hook(data: Dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            current = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            reporter.sync_update(
                "Downloading...",
                current,
                total,
                speed=data.get("speed"),
                eta=data.get("eta"),
            )
        elif status == "finished":
            total = data.get("total_bytes") or data.get("downloaded_bytes") or 0
            reporter.sync_update(
                "Processing downloaded file...",
                total,
                total,
                force=True,
            )

    return hook


def _upload_progress_callback(reporter: ProgressReporter):
    def callback(current: int, total: int) -> None:
        reporter.sync_update("Uploading to Telegram...", current, total)

    return callback


def _add_format(
    buttons: List[List[InlineKeyboardButton]],
    entry: VideoEntry,
    video_id: str,
    key: str,
    label: str,
    format_id: str,
) -> None:
    entry.formats[key] = format_id
    buttons.append([InlineKeyboardButton(label, callback_data=f"dl_{video_id}_{key}")])


def _build_format_keyboard(
    info: Dict[str, Any],
    video_id: str,
    entry: VideoEntry,
) -> InlineKeyboardMarkup:
    buttons: List[List[InlineKeyboardButton]] = []
    formats = info.get("formats", [])

    if not formats or (len(formats) == 1 and not formats[0].get("height")):
        _add_format(buttons, entry, video_id, "raw", "Download File/Subtitle", "raw")
        return InlineKeyboardMarkup(buttons)

    seen_heights = set()
    index = 0
    for item in formats:
        height = item.get("height")
        if height not in {360, 720, 1080} or height in seen_heights:
            continue

        key = f"f{index}"
        size = item.get("filesize") or item.get("filesize_approx")
        label = f"{height}p ({_format_size(size)})"
        _add_format(buttons, entry, video_id, key, label, item["format_id"])
        seen_heights.add(height)
        index += 1

    if not buttons:
        _add_format(buttons, entry, video_id, "best", "Best Quality", "best")

    return InlineKeyboardMarkup(buttons)


def register_handlers(app: Client, settings: Settings, cache: VideoCache) -> None:
    @app.on_message(filters.command(["start", "help"]))
    async def start_command(client: Client, message) -> None:
        if await reject_message_if_unauthorized(message, settings):
            return

        await message.reply(
            "**Video & Subtitle Downloader**\n\n"
            "Send a supported link and I will show available formats, download "
            "your choice, and upload it here with progress updates.\n\n"
            "Allowed users only."
        )

    @app.on_message(filters.regex(r"(https?://[^\s]+)"))
    async def handle_link(client: Client, message) -> None:
        if await reject_message_if_unauthorized(message, settings):
            return

        url = message.matches[0].group(1)
        status_message = await message.reply("Analyzing link...")

        try:
            video_id = make_video_id(url)
            info = await extract_info(url)
            entry = VideoEntry(info=info, url=url)
            cache.set(video_id, entry)
            keyboard = _build_format_keyboard(info, video_id, entry)
            title = _title(info)
            duration = info.get("duration")
            duration_text = (
                f"\nDuration: `{duration // 60}:{duration % 60:02d}`"
                if duration
                else ""
            )

            await status_message.edit(
                f"**Title:** `{title}`{duration_text}\nSelect format:",
                reply_markup=keyboard,
            )
        except Exception as exc:
            await status_message.edit(f"Error: {exc}")

    @app.on_callback_query(filters.regex(r"^dl_"))
    async def handle_download(client: Client, callback_query: CallbackQuery) -> None:
        if await reject_callback_if_unauthorized(callback_query, settings):
            return

        try:
            _, video_id, format_key = callback_query.data.split("_", 2)
        except (AttributeError, ValueError):
            await callback_query.answer("Format error.", show_alert=True)
            return

        entry = cache.get(video_id)
        if not entry:
            await callback_query.answer(
                "Session expired. Please send the link again.",
                show_alert=True,
            )
            return

        format_id = entry.formats.get(format_key)
        if not format_id:
            await callback_query.answer(
                "Format expired. Please send the link again.",
                show_alert=True,
            )
            return

        output_path: Path | None = None
        await callback_query.answer("Starting download...")
        reporter = ProgressReporter(callback_query.message, _title(entry.info))
        await reporter.start("Preparing download...")

        try:
            output_path = await download_media(
                entry.url,
                video_id,
                format_id,
                settings.download_dir,
                entry.info,
                progress_hook=_download_progress_hook(reporter),
            )
            await reporter.done(
                f"Download complete. Uploading `{output_path.name}` "
                f"({format_bytes(output_path.stat().st_size)})..."
            )
            upload_progress = _upload_progress_callback(reporter)

            if output_path.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                await client.send_video(
                    chat_id=callback_query.message.chat.id,
                    video=str(output_path),
                    caption=f"**{entry.info.get('title')}**",
                    supports_streaming=True,
                    progress=upload_progress,
                )
            else:
                await client.send_document(
                    chat_id=callback_query.message.chat.id,
                    document=str(output_path),
                    caption=f"**Subtitle/File:** `{entry.info.get('title')}`",
                    progress=upload_progress,
                )

            await reporter.done("Upload complete.")
            await callback_query.message.delete()
        except Exception as exc:
            await reporter.fail(f"Failed: {exc}")
        finally:
            if output_path and output_path.exists():
                output_path.unlink()
