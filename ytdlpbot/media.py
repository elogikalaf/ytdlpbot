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


async def download_media(
    url: str,
    download_id: str,
    format_id: str,
    output_dir: str,
    info: Dict[str, Any],
    progress_hook: Optional[ProgressHook] = None,
) -> Path:
    download_dir = Path(output_dir) / download_id
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded_path: Optional[Path] = None

    target_format = (
        "best" if format_id in {"raw", "best"} else f"{format_id}+bestaudio/best"
    )

    def track_progress(data: Dict[str, Any]) -> None:
        nonlocal downloaded_path
        filename = data.get("filename")
        if filename:
            downloaded_path = Path(filename)
        if progress_hook:
            progress_hook(data)

    ydl_opts = {
        "format": target_format,
        "outtmpl": str(download_dir / "%(title).200B [%(id)s].%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "progress_hooks": [track_progress],
    }

    await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
    if downloaded_path and downloaded_path.exists():
        return downloaded_path

    matches = [path for path in download_dir.iterdir() if path.is_file()]
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError("Downloaded file could not be found")
