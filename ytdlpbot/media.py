from __future__ import annotations

import asyncio
from email.message import Message
import hashlib
import logging
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yt_dlp

VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "mov"}
SUBTITLE_EXTENSIONS = {".vtt", ".srt", ".ass", ".ssa", ".ttml", ".dfxp", ".srv1", ".srv2", ".srv3"}
ProgressHook = Callable[[Dict[str, Any]], None]
logger = logging.getLogger(__name__)

_UNKNOWN_EXTENSIONS = {"", "part", "unknown", "unknown_video", "ytdl"}
_UNHELPFUL_MIME_EXTENSIONS = {".bat", ".c", ".ksh"}


def make_video_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _yt_dlp_options(cookies_file: Optional[str] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "quiet": True,
        "noplaylist": True,
        "js_runtimes": {
            "deno": {},
            "node": {},
            "quickjs": {},
            "bun": {},
        },
        "remote_components": ["ejs:github"],
    }
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


def _subtitle_candidates(download_dir: Path, media_path: Path) -> list[Path]:
    candidates: list[Path] = []
    for candidate in download_dir.iterdir():
        if not candidate.is_file() or candidate == media_path:
            continue
        suffix = candidate.suffix.lower()
        if suffix not in SUBTITLE_EXTENSIONS:
            continue
        if not candidate.name.startswith(media_path.stem):
            continue
        candidates.append(candidate)
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _is_subtitle_path(path: Path) -> bool:
    return path.suffix.lower() in SUBTITLE_EXTENSIONS


def _media_candidates(download_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for candidate in download_dir.iterdir():
        if not candidate.is_file():
            continue
        if _is_subtitle_path(candidate):
            continue
        if candidate.suffix.lower() == ".part":
            continue
        candidates.append(candidate)
    return candidates


async def download_media(
    url: str,
    download_id: str,
    format_id: str,
    output_dir: str,
    info: Dict[str, Any],
    audio_format_id: Optional[str] = None,
    progress_hook: Optional[ProgressHook] = None,
    cookies_file: Optional[str] = None,
    subtitle_language: Optional[str] = None,
) -> tuple[Path, Optional[Path]]:
    download_dir = Path(output_dir) / download_id
    download_dir.mkdir(parents=True, exist_ok=True)

    def _format_item(target_format_id: str) -> Optional[Dict[str, Any]]:
        for item in info.get("formats", []):
            if isinstance(item, dict) and str(item.get("format_id")) == target_format_id:
                return item
        return None

    def _exact_format_selector() -> Optional[str]:
        if format_id == "raw":
            if audio_format_id:
                return audio_format_id
            raw_format_id = info.get("format_id")
            return str(raw_format_id) if raw_format_id else None

        video_item = _format_item(format_id)
        selected_video_has_audio = bool(
            video_item and video_item.get("acodec") not in {None, "none"}
        )
        selected_audio_item = _format_item(audio_format_id) if audio_format_id else None
        selected_audio_is_audio_only = bool(
            selected_audio_item
            and selected_audio_item.get("acodec") not in {None, "none"}
            and selected_audio_item.get("vcodec") in {None, "none"}
        )

        # The previous implementation built selectors such as
        # "<video>+best audio" and then retried broader automatic selectors.
        # That loses the user's language choice on multilingual YouTube videos,
        # where original, dubbed, and generated audio are separate streams.
        if (
            audio_format_id
            and audio_format_id != format_id
            and selected_audio_is_audio_only
            and not selected_video_has_audio
        ):
            return f"{format_id}+{audio_format_id}"
        if audio_format_id:
            logger.warning(
                "Cannot cleanly merge selected audio format %s with video format %s; "
                "falling back to the exact video format.",
                audio_format_id,
                format_id,
            )
            return format_id
        return format_id

    def _clear_download_dir() -> None:
        for candidate in download_dir.iterdir():
            if candidate.is_file():
                candidate.unlink()

    def _download_once(target_format: Optional[str]) -> Optional[Path]:
        downloaded_path: Optional[Path] = None

        def track_progress(data: Dict[str, Any]) -> None:
            nonlocal downloaded_path
            filename = data.get("filename")
            if filename:
                candidate = Path(filename)
                if not _is_subtitle_path(candidate):
                    downloaded_path = candidate
            if progress_hook:
                progress_hook(data)

        ydl_opts = _yt_dlp_options(cookies_file)
        ydl_opts.update(
            {
                "outtmpl": str(download_dir / "%(title).200B [%(id)s].%(ext)s"),
                "progress_hooks": [track_progress],
            }
        )
        if target_format:
            ydl_opts["format"] = target_format
        if subtitle_language:
            ydl_opts.update(
                {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": [subtitle_language],
                    "subtitlesformat": "vtt/best",
                    "embedsubtitles": True,
                    "keep_subs": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegEmbedSubtitle",
                            "already_have_subtitle": True,
                        }
                    ],
                }
            )

        logger.debug(
            "Final yt-dlp format string: %s "
            "(video_format_id=%s audio_format_id=%s)",
            target_format,
            format_id,
            audio_format_id,
        )
        yt_dlp.YoutubeDL(ydl_opts).download([url])

        if (
            downloaded_path
            and downloaded_path.exists()
            and not _is_subtitle_path(downloaded_path)
        ):
            return downloaded_path

        matches = _media_candidates(download_dir)
        if len(matches) == 1:
            return matches[0]
        if matches:
            return max(matches, key=lambda p: p.stat().st_mtime)
        subtitle_matches = [
            p for p in download_dir.iterdir() if p.is_file() and _is_subtitle_path(p)
        ]
        if subtitle_matches:
            logger.warning(
                "yt-dlp produced subtitle files but no media file in %s: %s",
                download_dir,
                ", ".join(sorted(path.name for path in subtitle_matches)),
            )
        return None

    target_format = _exact_format_selector()
    _clear_download_dir()
    output_path = await asyncio.to_thread(_download_once, target_format)
    if output_path:
        output_path = await _fix_extension_if_needed(output_path, url, info)
        subtitle_path = None
        if subtitle_language:
            candidates = _subtitle_candidates(download_dir, output_path)
            subtitle_path = candidates[0] if candidates else None
        return output_path, subtitle_path

    subtitle_matches = [
        p for p in download_dir.iterdir() if p.is_file() and _is_subtitle_path(p)
    ]
    if subtitle_matches:
        raise FileNotFoundError(
            "yt-dlp downloaded subtitles but did not produce a media file"
        )

    raise FileNotFoundError("Downloaded media file could not be found")
