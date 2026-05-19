from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yt_dlp


VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "mov"}
ProgressHook = Callable[[Dict[str, Any]], None]


def make_video_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


async def extract_info(url: str) -> Dict[str, Any]:
    def _extract() -> Dict[str, Any]:
        ydl_opts = {"quiet": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return ydl.sanitize_info(info)

    return await asyncio.to_thread(_extract)


def choose_extension(url: str, info: Dict[str, Any]) -> str:
    url_lower = url.lower()
    if "subtitle" in url_lower or "vtt" in url_lower:
        return "vtt"
    if "m3u8" in url_lower:
        return "mp4"
    return info.get("ext", "mp4")


async def download_media(
    url: str,
    video_id: str,
    format_id: str,
    output_dir: str,
    info: Dict[str, Any],
    progress_hook: Optional[ProgressHook] = None,
) -> Path:
    output_path = Path(output_dir) / f"file_{video_id}.{choose_extension(url, info)}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    target_format = (
        "best" if format_id in {"raw", "best"} else f"{format_id}+bestaudio/best"
    )
    ydl_opts = {
        "format": target_format,
        "outtmpl": str(output_path),
        "quiet": True,
        "noplaylist": True,
    }
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
    return output_path
