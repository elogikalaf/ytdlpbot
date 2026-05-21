from __future__ import annotations

import asyncio
from email.message import Message
import hashlib
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yt_dlp

VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "mov"}
ProgressHook = Callable[[Dict[str, Any]], None]

_UNKNOWN_EXTENSIONS = {"", "part", "unknown", "unknown_video", "ytdl"}
_UNHELPFUL_MIME_EXTENSIONS = {".bat", ".c", ".ksh"}


def make_video_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _yt_dlp_options(cookies_file: Optional[str] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {"quiet": True, "noplaylist": True}
    if cookies_file:
        options["cookiefile"] = cookies_file
    return options


async def extract_info(url: str, cookies_file: Optional[str] = None) -> Dict[str, Any]:
    def _extract() -> Dict[str, Any]:
        ydl_opts = _yt_dlp_options(cookies_file)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return ydl.sanitize_info(info)

    return await asyncio.to_thread(_extract)


def _safe_filename(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    filename = Path(urllib.parse.unquote(str(name).strip())).name
    return filename or None


def _filename_from_content_disposition(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    message = Message()
    message["content-disposition"] = value
    return _safe_filename(message.get_filename())


def _filename_from_url(url: str) -> Optional[str]:
    path = urllib.parse.urlparse(url).path
    filename = _safe_filename(path.rstrip("/").rsplit("/", 1)[-1])
    if filename and "." in filename:
        return filename
    return None


def _extension_from_content_type(value: Optional[str]) -> str:
    if not value:
        return ""

    content_type = value.split(";", 1)[0].strip().lower()
    extension = mimetypes.guess_extension(content_type) or ""
    if extension in _UNHELPFUL_MIME_EXTENSIONS:
        return ""
    return extension


def _headers_from_info(info: Dict[str, Any], *, range_probe: bool = False) -> Dict[str, str]:
    headers = {
        str(key): str(value)
        for key, value in info.get("http_headers", {}).items()
        if value is not None
    }
    if range_probe:
        headers["Range"] = "bytes=0-0"
    return headers


def _probe_response(url: str, info: Dict[str, Any]) -> Any:
    requests = (
        Request(url, headers=_headers_from_info(info), method="HEAD"),
        Request(url, headers=_headers_from_info(info, range_probe=True), method="GET"),
    )

    last_error: Exception | None = None
    for request in requests:
        try:
            return urlopen(request, timeout=15)
        except (HTTPError, URLError) as exc:
            last_error = exc

    if last_error:
        raise last_error
    raise RuntimeError("Could not probe download response")


def _resolve_real_filename(url: str, current_stem: str, info: Dict[str, Any]) -> Optional[str]:
    """
    Follow redirects and inspect response headers to find the real filename.
    Returns a filename string (with extension) or None if nothing useful is found.
    """
    try:
        with _probe_response(url, info) as response:
            headers = response.headers
            final_url = response.geturl()

            filename = _filename_from_content_disposition(
                headers.get("Content-Disposition")
            )
            if filename:
                return filename

            filename = _filename_from_url(final_url)
            if filename:
                return filename

            extension = _extension_from_content_type(headers.get("Content-Type"))
            if extension:
                return f"{current_stem}{extension}"
    except (HTTPError, URLError, OSError, RuntimeError):
        return None

    return None


async def _fix_extension_if_needed(path: Path, url: str, info: Dict[str, Any]) -> Path:
    """
    If yt-dlp produced a file with a missing or placeholder extension,
    resolve the real filename via HTTP headers and rename accordingly.
    """
    if path.suffix.lstrip(".").lower() not in _UNKNOWN_EXTENSIONS:
        return path

    real_name = await asyncio.to_thread(_resolve_real_filename, url, path.stem, info)
    if not real_name:
        return path

    new_path = path.with_name(real_name)
    if new_path == path or new_path.exists():
        return path

    path.rename(new_path)
    return new_path


async def download_media(
    url: str,
    download_id: str,
    format_id: str,
    output_dir: str,
    info: Dict[str, Any],
    progress_hook: Optional[ProgressHook] = None,
    cookies_file: Optional[str] = None,
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

    ydl_opts = _yt_dlp_options(cookies_file)
    ydl_opts.update({
        "format": target_format,
        "outtmpl": str(download_dir / "%(title).200B [%(id)s].%(ext)s"),
        "progress_hooks": [track_progress],
    })

    await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

    if downloaded_path and downloaded_path.exists():
        output_path = downloaded_path
    else:
        matches = [p for p in download_dir.iterdir() if p.is_file()]
        if len(matches) == 1:
            output_path = matches[0]
        else:
            raise FileNotFoundError("Downloaded file could not be found")

    return await _fix_extension_if_needed(output_path, url, info)
