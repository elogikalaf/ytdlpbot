from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ytdlpbot.auth import (
    reject_callback_if_unauthorized,
    reject_message_if_unauthorized,
)
from ytdlpbot.cache import AudioTrack, SubtitleChoice, VideoCache, VideoEntry
from ytdlpbot.config import Settings
from ytdlpbot.media import VIDEO_EXTENSIONS, download_media, extract_info, make_video_id
from ytdlpbot.progress import ProgressReporter, format_bytes


_VIDEO_HEIGHTS = {144, 240, 360, 480, 720, 1080, 1440, 2160}
_SUBTITLE_CALLBACK_PREFIX = "sub"
_AUDIO_CALLBACK_PREFIX = "aud"
_DOWNLOAD_CALLBACK_PREFIX = "dl"
_NAV_CALLBACK_PREFIX = "nav"
_MAX_SUBTITLE_BUTTONS = 8
_PREFERRED_SUBTITLE_LANGUAGES = (
    "en",
    "fa",
    "es",
    "fr",
    "de",
    "ar",
    "tr",
    "ru",
)
_LANGUAGE_NAMES = {
    "aa": "Afar",
    "ab": "Abkhazian",
    "ae": "Avestan",
    "af": "Afrikaans",
    "ak": "Akan",
    "am": "Amharic",
    "an": "Aragonese",
    "ar": "Arabic",
    "as": "Assamese",
    "av": "Avaric",
    "ay": "Aymara",
    "az": "Azerbaijani",
    "ba": "Bashkir",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bh": "Bihari",
    "bi": "Bislama",
    "bm": "Bambara",
    "bn": "Bengali",
    "bo": "Tibetan",
    "br": "Breton",
    "bs": "Bosnian",
    "ca": "Catalan",
    "ce": "Chechen",
    "ch": "Chamorro",
    "co": "Corsican",
    "cr": "Cree",
    "cs": "Czech",
    "cu": "Church Slavic",
    "cv": "Chuvash",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "dv": "Divehi",
    "dz": "Dzongkha",
    "ee": "Ewe",
    "el": "Greek",
    "en": "English",
    "en-us": "English",
    "en-gb": "English",
    "eo": "Esperanto",
    "es": "Spanish",
    "et": "Estonian",
    "eu": "Basque",
    "fa": "Persian",
    "ff": "Fulah",
    "fi": "Finnish",
    "fj": "Fijian",
    "fo": "Faroese",
    "fr": "French",
    "fy": "Western Frisian",
    "ga": "Irish",
    "gd": "Scottish Gaelic",
    "gl": "Galician",
    "gn": "Guarani",
    "gu": "Gujarati",
    "gv": "Manx",
    "ha": "Hausa",
    "he": "Hebrew",
    "hi": "Hindi",
    "ho": "Hiri Motu",
    "hr": "Croatian",
    "ht": "Haitian Creole",
    "hu": "Hungarian",
    "hy": "Armenian",
    "hz": "Herero",
    "ia": "Interlingua",
    "id": "Indonesian",
    "ie": "Interlingue",
    "ig": "Igbo",
    "ii": "Sichuan Yi",
    "ik": "Inupiaq",
    "io": "Ido",
    "is": "Icelandic",
    "it": "Italian",
    "iu": "Inuktitut",
    "ja": "Japanese",
    "jv": "Javanese",
    "ka": "Georgian",
    "kg": "Kongo",
    "ki": "Kikuyu",
    "kj": "Kuanyama",
    "kk": "Kazakh",
    "kl": "Kalaallisut",
    "km": "Khmer",
    "kn": "Kannada",
    "ko": "Korean",
    "kr": "Kanuri",
    "ks": "Kashmiri",
    "ku": "Kurdish",
    "kv": "Komi",
    "kw": "Cornish",
    "ky": "Kyrgyz",
    "la": "Latin",
    "lb": "Luxembourgish",
    "lg": "Ganda",
    "li": "Limburgish",
    "ln": "Lingala",
    "lo": "Lao",
    "lt": "Lithuanian",
    "lu": "Luba-Katanga",
    "lv": "Latvian",
    "mg": "Malagasy",
    "mh": "Marshallese",
    "mi": "Maori",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mn": "Mongolian",
    "mr": "Marathi",
    "ms": "Malay",
    "mt": "Maltese",
    "my": "Burmese",
    "na": "Nauru",
    "nb": "Norwegian Bokmal",
    "nd": "Northern Ndebele",
    "ne": "Nepali",
    "ng": "Ndonga",
    "nl": "Dutch",
    "nn": "Norwegian Nynorsk",
    "no": "Norwegian",
    "nr": "Southern Ndebele",
    "nv": "Navajo",
    "ny": "Nyanja",
    "oc": "Occitan",
    "oj": "Ojibwa",
    "om": "Oromo",
    "or": "Odia",
    "os": "Ossetian",
    "pa": "Punjabi",
    "pi": "Pali",
    "pl": "Polish",
    "ps": "Pashto",
    "pt": "Portuguese",
    "pt-br": "Portuguese",
    "qu": "Quechua",
    "rm": "Romansh",
    "rn": "Rundi",
    "ro": "Romanian",
    "ru": "Russian",
    "rw": "Kinyarwanda",
    "sa": "Sanskrit",
    "sc": "Sardinian",
    "sd": "Sindhi",
    "se": "Northern Sami",
    "sg": "Sango",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sm": "Samoan",
    "sn": "Shona",
    "so": "Somali",
    "sq": "Albanian",
    "sr": "Serbian",
    "ss": "Swati",
    "st": "Southern Sotho",
    "su": "Sundanese",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "tg": "Tajik",
    "th": "Thai",
    "ti": "Tigrinya",
    "tk": "Turkmen",
    "tl": "Tagalog",
    "tn": "Tswana",
    "to": "Tongan",
    "tr": "Turkish",
    "ts": "Tsonga",
    "tt": "Tatar",
    "tw": "Twi",
    "ty": "Tahitian",
    "ug": "Uyghur",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "ve": "Venda",
    "vi": "Vietnamese",
    "vo": "Volapuk",
    "wa": "Walloon",
    "wo": "Wolof",
    "xh": "Xhosa",
    "yi": "Yiddish",
    "yo": "Yoruba",
    "za": "Zhuang",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "zh-hans": "Chinese",
    "zh-hant": "Chinese",
    "zh-tw": "Chinese",
    "zu": "Zulu",
}

logger = logging.getLogger(__name__)


def _positive_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _format_size(size: Any, *, estimated: bool = False) -> str:
    parsed_size = _positive_float(size)
    if parsed_size is None:
        return "unknown size"

    prefix = "~" if estimated else ""
    return f"{prefix}{format_bytes(parsed_size)}"


def _title(info: Dict[str, Any]) -> str:
    return str(info.get("title") or "Untitled")[:60]


def _download_status_label(
    data: Dict[str, Any],
    video_format_id: Optional[str],
    audio_format_id: Optional[str],
) -> str:
    info = data.get("info_dict")
    if not isinstance(info, dict):
        return "Downloading..."

    current_format_id = info.get("format_id")
    if current_format_id is not None:
        current_format_id = str(current_format_id)
    if audio_format_id and current_format_id == audio_format_id:
        return "Downloading audio..."
    if video_format_id and current_format_id == video_format_id:
        return "Downloading video..."

    acodec = info.get("acodec")
    vcodec = info.get("vcodec")
    if acodec not in {None, "none"} and vcodec in {None, "none"}:
        return "Downloading audio..."
    if vcodec not in {None, "none"}:
        return "Downloading video..."

    return "Downloading..."


def _download_progress_hook(
    reporter: ProgressReporter,
    video_format_id: Optional[str],
    audio_format_id: Optional[str],
):
    def hook(data: Dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            current = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if total and current >= total:
                return
            reporter.sync_update(
                _download_status_label(data, video_format_id, audio_format_id),
                current,
                total,
                speed=data.get("speed"),
                eta=data.get("eta"),
            )
        elif status == "finished":
            # yt-dlp fires this for each selected stream. For exact video+audio
            # downloads, forcing a 100% bar here makes short audio streams look
            # stuck before the next phase starts. Show a neutral transition
            # message instead and let the next progress event draw the bar.
            reporter.sync_done("Processing downloaded streams...")

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
    buttons.append(
        [
            InlineKeyboardButton(
                label,
                callback_data=f"{_DOWNLOAD_CALLBACK_PREFIX}_{video_id}_{key}",
            )
        ]
    )


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _track_name(tracks: Any) -> Optional[str]:
    if not isinstance(tracks, list):
        return None

    for track in tracks:
        if not isinstance(track, dict):
            continue
        name = track.get("name")
        if name:
            return str(name)

    return None


def _clean_language_code(language: str) -> str:
    return language.split("-", 1)[0].split("_", 1)[0].lower()


def _language_name(language: str, tracks: Any = None) -> str:
    track_name = _track_name(tracks)
    if track_name:
        return track_name

    normalized = language.replace("_", "-").lower()
    if normalized in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[normalized]

    base_language = _clean_language_code(language)
    if base_language in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[base_language]

    return f"Language: {language}"


def _is_audio_capable_format(item: Dict[str, Any]) -> bool:
    return item.get("acodec") not in {None, "none"}


def _audio_language_display(language: Optional[str]) -> str:
    if not language:
        return "Unknown audio"
    return _language_name(language)


def _is_original_audio(item: Dict[str, Any]) -> bool:
    note = str(item.get("format_note") or "").lower()
    format_id = str(item.get("format_id") or "")
    return "original" in note or format_id.endswith("-0")


def _is_default_audio(item: Dict[str, Any]) -> bool:
    note = str(item.get("format_note") or "").lower()
    language_preference = _optional_int(item.get("language_preference"))
    return bool(language_preference and language_preference > 0) or "default" in note


def _audio_track_from_format(item: Dict[str, Any]) -> Optional[AudioTrack]:
    format_id = item.get("format_id")
    if not format_id:
        return None

    language = item.get("language")
    if language is not None:
        language = str(language)

    return AudioTrack(
        format_id=str(format_id),
        language=language,
        language_display=_audio_language_display(language),
        is_default=_is_default_audio(item),
        is_original=_is_original_audio(item),
        is_audio_only=_is_audio_format(item),
        abr=_positive_float(item.get("abr")),
        source_preference=_optional_int(item.get("source_preference")),
        language_preference=_optional_int(item.get("language_preference")),
        format_note=str(item.get("format_note")) if item.get("format_note") else None,
    )


def _audio_default_score(track: AudioTrack, index: int) -> tuple[int, int, int]:
    # YouTube now exposes original, dubbed, and sometimes generated audio as
    # separate streams. The old code kept only the chosen video id and let
    # yt-dlp auto-pick audio later, so a Spanish dub could replace English.
    # Keep this ranking deterministic and use the winning exact format id.
    if track.language_preference is not None and track.language_preference > 0:
        return 5, track.language_preference, -index
    if track.is_original:
        return 4, 0, -index
    if track.is_default:
        return 3, 0, -index
    if track.format_id.endswith("-0"):
        return 2, 0, -index
    if track.source_preference is not None:
        return 1, track.source_preference, -index
    return 0, 0, -index


def _select_default_audio_key(entry: VideoEntry) -> Optional[str]:
    if not entry.audio_tracks:
        return None
    audio_only_keys = [
        key for key, track in entry.audio_tracks.items() if track.is_audio_only
    ]
    candidate_keys = audio_only_keys or list(entry.audio_tracks)
    return max(
        candidate_keys,
        key=lambda key: _audio_default_score(
            entry.audio_tracks[key],
            candidate_keys.index(key),
        ),
    )


def _store_audio_tracks(entry: VideoEntry, info: Dict[str, Any]) -> None:
    entry.audio_tracks.clear()
    entry.selected_audio_key = None

    # Preserve every audio-capable yt-dlp format. Multilingual YouTube videos
    # often provide one audio-only stream per language/dub, and automatic
    # "best audio" selection is not language-safe across extractor changes.
    audio_formats = [
        item
        for item in info.get("formats", [])
        if isinstance(item, dict) and _is_audio_capable_format(item)
    ]

    for index, item in enumerate(audio_formats):
        track = _audio_track_from_format(item)
        if track is None:
            continue

        key = f"a{index}"
        entry.audio_tracks[key] = track
        logger.debug(
            "Detected audio track: key=%s format_id=%s language=%s display=%s "
            "default=%s original=%s audio_only=%s abr=%s source_preference=%s "
            "language_preference=%s format_note=%s",
            key,
            track.format_id,
            track.language,
            track.language_display,
            track.is_default,
            track.is_original,
            track.is_audio_only,
            track.abr,
            track.source_preference,
            track.language_preference,
            track.format_note,
        )

    entry.selected_audio_key = _select_default_audio_key(entry)
    selected = _selected_audio(entry)
    if selected:
        logger.debug(
            "Selected default audio track: key=%s format_id=%s language=%s label=%s",
            entry.selected_audio_key,
            selected.format_id,
            selected.language,
            _audio_label(selected),
        )


def _selected_audio(entry: VideoEntry) -> Optional[AudioTrack]:
    if entry.selected_audio_key is None:
        return None
    return entry.audio_tracks.get(entry.selected_audio_key)


def _audio_label(track: AudioTrack) -> str:
    details: list[str] = []
    note = (track.format_note or "").lower()
    if track.is_original:
        details.append("Original")
    elif track.is_default:
        details.append("Default")
    if not track.is_audio_only:
        details.append("Muxed")
    if "dub" in note:
        details.append("Dubbed")
    if "generated" in note or "auto" in note:
        details.append("Generated")
    if track.abr:
        details.append(f"{track.abr:g}k")

    suffix = f" ({', '.join(dict.fromkeys(details))})" if details else ""
    return f"{track.language_display}{suffix}"[:48]


def _audio_status(entry: VideoEntry) -> str:
    selected = _selected_audio(entry)
    return _audio_label(selected) if selected else "None"


def _format_duration_text(info: Dict[str, Any]) -> str:
    duration = info.get("duration")
    if not duration:
        return ""
    return f"\nDuration: `{duration // 60}:{duration % 60:02d}`"


def _screen_text(entry: VideoEntry, step: str) -> str:
    title = _title(entry.info)
    if step == "audio":
        return (
            f"**Title:** `{title}`{_format_duration_text(entry.info)}\n"
            "Step 1/3: Choose audio"
        )
    if step == "subtitle":
        return (
            f"**Title:** `{title}`{_format_duration_text(entry.info)}\n"
            f"Audio: `{_audio_status(entry)}`\n"
            "Step 2/3: Choose subtitles"
        )
    return (
        f"**Title:** `{title}`{_format_duration_text(entry.info)}\n"
        f"Audio: `{_audio_status(entry)}`\n"
        f"Subtitles: `{_subtitle_status(entry)}`\n"
        "Step 3/3: Choose video quality"
    )


def _edit_step_message(
    callback_query: CallbackQuery,
    video_id: str,
    entry: VideoEntry,
    step: str,
):
    step = _screen_for_step(entry, step)
    entry.current_step = step
    keyboard = _step_keyboard(video_id, entry, step)
    if keyboard is None:
        return callback_query.message.edit(
            f"**Title:** `{_title(entry.info)}`{_format_duration_text(entry.info)}\n"
            "No downloadable video formats were found. On YouTube this usually "
            "means the VPS still needs yt-dlp challenge support and a JavaScript runtime."
        )
    return callback_query.message.edit(
        _screen_text(entry, step),
        reply_markup=keyboard,
    )


def _navigation_button(video_id: str, target_step: str, label: str) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                label,
                callback_data=f"{_NAV_CALLBACK_PREFIX}_{video_id}_{target_step}",
            )
        ]
    ]


def _audio_format_item(info: Dict[str, Any], track: Optional[AudioTrack]) -> Optional[Dict[str, Any]]:
    if not track:
        return None
    for item in info.get("formats", []):
        if isinstance(item, dict) and str(item.get("format_id")) == track.format_id:
            return item
    return None


def _audio_variant_key(track: AudioTrack) -> tuple[str, bool, bool, bool, bool]:
    note = (track.format_note or "").lower()
    return (
        (track.language or track.language_display).lower(),
        track.is_original,
        track.is_default,
        "dub" in note,
        "generated" in note or "auto" in note,
    )


def _visible_audio_items(entry: VideoEntry) -> list[tuple[str, AudioTrack]]:
    source_items = [
        (key, track) for key, track in entry.audio_tracks.items() if track.is_audio_only
    ] or list(entry.audio_tracks.items())
    best_by_variant: dict[tuple[str, bool, bool, bool, bool], tuple[str, AudioTrack, int]] = {}

    for index, (key, track) in enumerate(source_items):
        variant_key = _audio_variant_key(track)
        current = best_by_variant.get(variant_key)
        if current is None:
            best_by_variant[variant_key] = (key, track, index)
            continue

        _, current_track, current_index = current
        candidate_score = (
            _audio_default_score(track, index),
            track.abr or 0,
        )
        current_score = (
            _audio_default_score(current_track, current_index),
            current_track.abr or 0,
        )
        if candidate_score > current_score:
            best_by_variant[variant_key] = (key, track, index)

    return [
        (key, track)
        for key, track, _ in sorted(
            best_by_variant.values(),
            key=lambda item: (
                -_audio_default_score(item[1], item[2])[0],
                item[1].language_display,
                item[2],
            ),
        )
    ]


def _audio_buttons(video_id: str, entry: VideoEntry) -> list[list[InlineKeyboardButton]]:
    if not entry.audio_tracks:
        return []

    rows: list[list[InlineKeyboardButton]] = []
    for key, track in _visible_audio_items(entry):
        prefix = "[x] " if key == entry.selected_audio_key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix}{_audio_label(track)}",
                    callback_data=f"{_AUDIO_CALLBACK_PREFIX}_{video_id}_{key}",
                )
            ]
        )

    return rows


def _needs_audio_step(entry: VideoEntry) -> bool:
    return len(_visible_audio_items(entry)) > 1


def _subtitle_label(language: str, source: str, tracks: Any) -> str:
    label = _language_name(language, tracks)
    if source == "automatic_captions":
        label = f"{label} (generated)"
    return label[:32]


def _subtitle_sources(info: Dict[str, Any]) -> list[tuple[str, Dict[str, Any]]]:
    return [
        ("subtitles", info.get("subtitles") or {}),
        ("automatic_captions", info.get("automatic_captions") or {}),
    ]


def _available_subtitles(info: Dict[str, Any]) -> list[SubtitleChoice]:
    choices: list[SubtitleChoice] = [
        SubtitleChoice(language=None, label="No subtitles", source="none")
    ]
    seen_languages: set[str] = set()
    subtitle_items: list[tuple[str, str, Any]] = []

    for source, subtitles in _subtitle_sources(info):
        subtitle_items.extend(
            (source, language, tracks)
            for language, tracks in subtitles.items()
            if tracks
        )

    for source, language, tracks in _ranked_subtitle_items(subtitle_items):
        if language in seen_languages:
            continue
        choices.append(
            SubtitleChoice(
                language=language,
                label=_subtitle_label(language, source, tracks),
                source=source,
            )
        )
        seen_languages.add(language)
        if len(choices) >= _MAX_SUBTITLE_BUTTONS + 1:
            return choices

    return choices


def _ranked_subtitle_items(
    subtitles: list[tuple[str, str, Any]],
) -> list[tuple[str, str, Any]]:
    def sort_key(item: tuple[str, str, Any]) -> tuple[int, int, str]:
        source, language, _ = item
        normalized = language.replace("_", "-").lower()
        base_language = _clean_language_code(language)
        try:
            preferred_index = _PREFERRED_SUBTITLE_LANGUAGES.index(normalized)
        except ValueError:
            try:
                preferred_index = _PREFERRED_SUBTITLE_LANGUAGES.index(base_language)
            except ValueError:
                preferred_index = len(_PREFERRED_SUBTITLE_LANGUAGES)

        known_language = 0 if base_language in _LANGUAGE_NAMES else 1
        source_rank = 0 if source == "subtitles" else 1
        return preferred_index, known_language, source_rank, normalized

    return sorted(subtitles, key=sort_key)


def _store_subtitle_choices(entry: VideoEntry, info: Dict[str, Any]) -> None:
    entry.subtitles.clear()
    for index, choice in enumerate(_available_subtitles(info)):
        key = "none" if choice.language is None else f"s{index}"
        entry.subtitles[key] = choice
    entry.selected_subtitle_key = "none"


def _selected_subtitle(entry: VideoEntry) -> SubtitleChoice:
    return entry.subtitles.get(
        entry.selected_subtitle_key,
        SubtitleChoice(language=None, label="No subtitles", source="none"),
    )


def _subtitle_status(entry: VideoEntry) -> str:
    selected = _selected_subtitle(entry)
    return selected.label if selected.language else "None"


def _subtitle_buttons(video_id: str, entry: VideoEntry) -> list[list[InlineKeyboardButton]]:
    if len(entry.subtitles) <= 1:
        return []

    rows: list[list[InlineKeyboardButton]] = []
    for key, choice in entry.subtitles.items():
        prefix = "[x] " if key == entry.selected_subtitle_key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix}{choice.label}",
                    callback_data=f"{_SUBTITLE_CALLBACK_PREFIX}_{video_id}_{key}",
                )
            ]
        )

    return rows


def _is_downloadable_video_format(item: Dict[str, Any]) -> bool:
    if not item.get("height"):
        return False
    if item.get("vcodec") in {None, "none"}:
        return False

    ext = str(item.get("ext") or "").lower()
    if ext in {"gif", "jpg", "jpeg", "mhtml", "png", "webp"}:
        return False

    protocol = str(item.get("protocol") or "").lower()
    if protocol in {"mhtml", "images"}:
        return False

    note = str(item.get("format_note") or "").lower()
    return not any(value in note for value in ("storyboard", "thumbnail", "image"))


def _is_audio_format(item: Dict[str, Any]) -> bool:
    return item.get("acodec") not in {None, "none"} and item.get("vcodec") in {
        None,
        "none",
    }


def _duration_seconds(info: Dict[str, Any]) -> Optional[float]:
    return _positive_float(info.get("duration"))


def _bitrate_size(item: Dict[str, Any], duration: Optional[float]) -> Optional[float]:
    if duration is None:
        return None

    bitrate = _positive_float(item.get("tbr"))
    if bitrate is None:
        if _is_audio_format(item):
            bitrate = _positive_float(item.get("abr"))
        else:
            bitrate = _positive_float(item.get("vbr"))

    if bitrate is None:
        return None

    return bitrate * 1000 / 8 * duration


def _item_size(item: Dict[str, Any], duration: Optional[float]) -> tuple[Optional[float], bool]:
    filesize = _positive_float(item.get("filesize"))
    if filesize is not None:
        return filesize, False

    filesize_approx = _positive_float(item.get("filesize_approx"))
    if filesize_approx is not None:
        return filesize_approx, True

    bitrate_size = _bitrate_size(item, duration)
    if bitrate_size is not None:
        return bitrate_size, True

    return None, False


def _download_size_label(
    item: Dict[str, Any],
    audio_format: Optional[Dict[str, Any]],
    duration: Optional[float],
) -> str:
    total_size, estimated = _item_size(item, duration)
    if total_size is None:
        return _format_size(None)

    if item.get("acodec") in {None, "none"} and audio_format:
        audio_size, audio_estimated = _item_size(audio_format, duration)
        if audio_size is not None:
            total_size += audio_size
            estimated = estimated or audio_estimated

    return _format_size(total_size, estimated=estimated)


def _best_video_by_height(info: Dict[str, Any]) -> list[Dict[str, Any]]:
    formats = info.get("formats", [])
    duration = _duration_seconds(info)
    height_map: dict[int, list[tuple[int, Dict[str, Any]]]] = {}

    for index, item in enumerate(formats):
        if not isinstance(item, dict) or not _is_downloadable_video_format(item):
            continue
        height = item.get("height")
        if height not in _VIDEO_HEIGHTS:
            continue
        height_map.setdefault(height, []).append((index, item))

    def score(candidate: tuple[int, Dict[str, Any]]) -> tuple[int, float, float, int]:
        index, item = candidate
        # Prefer video-only streams for clean explicit video+audio merging, but
        # keep muxed formats as candidates so qualities like 720p/1080p do not
        # disappear when YouTube exposes them only as combined streams.
        audio_free = 1 if item.get("acodec") in {None, "none"} else 0
        bitrate = _positive_float(item.get("vbr")) or _positive_float(item.get("tbr")) or 0
        size, _ = _item_size(item, duration)
        return audio_free, bitrate, size or 0, -index

    return [
        max(height_map[height], key=score)[1]
        for height in sorted(height_map, reverse=True)
    ]


def _store_video_choices(entry: VideoEntry, info: Dict[str, Any]) -> None:
    entry.formats.clear()
    entry.selected_video_key = None

    for index, item in enumerate(_best_video_by_height(info)):
        key = f"f{index}"
        entry.formats[key] = str(item["format_id"])

    if entry.formats:
        entry.selected_video_key = next(iter(entry.formats))
    elif entry.audio_tracks or info.get("format_id"):
        entry.formats["raw"] = "raw"
        entry.selected_video_key = "raw"


def _video_buttons(video_id: str, entry: VideoEntry) -> list[list[InlineKeyboardButton]]:
    if not entry.formats:
        return []

    rows: list[list[InlineKeyboardButton]] = []
    duration = _duration_seconds(entry.info)
    audio_format = _audio_format_item(entry.info, _selected_audio(entry))

    for key, format_id in entry.formats.items():
        if format_id == "raw":
            label = "Download Selected Audio" if entry.audio_tracks else "Download File"
        else:
            item = next(
                (
                    item
                    for item in entry.info.get("formats", [])
                    if isinstance(item, dict) and str(item.get("format_id")) == format_id
                ),
                None,
            )
            if item is None:
                continue
            height = item.get("height")
            label = f"{height}p ({_download_size_label(item, audio_format, duration)})"

        prefix = "[x] " if key == entry.selected_video_key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix}{label}",
                    callback_data=f"{_DOWNLOAD_CALLBACK_PREFIX}_{video_id}_{key}",
                )
            ]
        )

    return rows


def _step_keyboard(video_id: str, entry: VideoEntry, step: str) -> Optional[InlineKeyboardMarkup]:
    if step == "audio" and not _needs_audio_step(entry):
        step = "subtitle"

    if step == "audio":
        rows = _audio_buttons(video_id, entry)
        rows.extend(_navigation_button(video_id, "subtitle", "Next: Subtitles"))
        return InlineKeyboardMarkup(rows)

    if step == "subtitle":
        rows = _subtitle_buttons(video_id, entry)
        if not rows:
            rows = [
                [
                    InlineKeyboardButton(
                        "[x] No subtitles",
                        callback_data=f"{_SUBTITLE_CALLBACK_PREFIX}_{video_id}_none",
                    )
                ]
            ]
        if _needs_audio_step(entry):
            rows.extend(_navigation_button(video_id, "audio", "Back: Audio"))
        rows.extend(_navigation_button(video_id, "video", "Next: Video Quality"))
        return InlineKeyboardMarkup(rows)

    rows = _video_buttons(video_id, entry)
    if not rows:
        return None
    back_step = "subtitle" if len(entry.subtitles) > 1 else "audio"
    if back_step == "audio" and not _needs_audio_step(entry):
        back_step = ""
    if back_step:
        rows.extend(
            _navigation_button(
                video_id,
                back_step,
                "Back: Subtitles" if back_step == "subtitle" else "Back: Audio",
            )
        )
    return InlineKeyboardMarkup(rows)


def _screen_for_step(entry: VideoEntry, step: str) -> str:
    if step == "audio" and not _needs_audio_step(entry):
        step = "subtitle"
    if step == "video":
        return "video"
    if step == "subtitle" and len(entry.subtitles) <= 1:
        return "video"
    return step


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
            info = await extract_info(url, cookies_file=settings.cookies_file)
            entry = VideoEntry(info=info, url=url)
            _store_subtitle_choices(entry, info)
            _store_audio_tracks(entry, info)
            _store_video_choices(entry, info)
            cache.set(video_id, entry)
            step = _screen_for_step(entry, "audio")
            entry.current_step = step
            keyboard = _step_keyboard(video_id, entry, step)

            if keyboard is None:
                await status_message.edit(
                    f"**Title:** `{_title(info)}`{_format_duration_text(info)}\n"
                    "No downloadable video formats were found. On YouTube this "
                    "usually means the VPS still needs yt-dlp challenge support "
                    "and a JavaScript runtime."
                )
                return

            await status_message.edit(
                _screen_text(entry, step),
                reply_markup=keyboard,
            )
        except Exception as exc:
            await status_message.edit(f"Error: {exc}")

    @app.on_callback_query(filters.regex(r"^sub_"))
    async def handle_subtitle_selection(client: Client, callback_query: CallbackQuery) -> None:
        if await reject_callback_if_unauthorized(callback_query, settings):
            return

        try:
            _, video_id, subtitle_key = callback_query.data.split("_", 2)
        except (AttributeError, ValueError):
            await callback_query.answer("Subtitle error.", show_alert=True)
            return

        entry = cache.get(video_id)
        if not entry:
            await callback_query.answer(
                "Session expired. Please send the link again.",
                show_alert=True,
            )
            return

        if subtitle_key not in entry.subtitles:
            await callback_query.answer(
                "Subtitle expired. Please send the link again.",
                show_alert=True,
            )
            return

        entry.selected_subtitle_key = subtitle_key
        step = _screen_for_step(entry, "video")
        await _edit_step_message(callback_query, video_id, entry, step)
        await callback_query.answer(f"Subtitles: {_subtitle_status(entry)}")

    @app.on_callback_query(filters.regex(r"^aud_"))
    async def handle_audio_selection(client: Client, callback_query: CallbackQuery) -> None:
        if await reject_callback_if_unauthorized(callback_query, settings):
            return

        try:
            _, video_id, audio_key = callback_query.data.split("_", 2)
        except (AttributeError, ValueError):
            await callback_query.answer("Audio error.", show_alert=True)
            return

        entry = cache.get(video_id)
        if not entry:
            await callback_query.answer(
                "Session expired. Please send the link again.",
                show_alert=True,
            )
            return

        if audio_key not in entry.audio_tracks:
            await callback_query.answer(
                "Audio track expired. Please send the link again.",
                show_alert=True,
            )
            return

        entry.selected_audio_key = audio_key
        selected_audio = _selected_audio(entry)
        if selected_audio:
            logger.debug(
                "User selected audio track: key=%s format_id=%s language=%s label=%s",
                audio_key,
                selected_audio.format_id,
                selected_audio.language,
                _audio_label(selected_audio),
            )

        step = _screen_for_step(entry, "subtitle")
        await _edit_step_message(callback_query, video_id, entry, step)
        await callback_query.answer(f"Audio: {_audio_status(entry)}")

    @app.on_callback_query(filters.regex(r"^nav_"))
    async def handle_step_navigation(client: Client, callback_query: CallbackQuery) -> None:
        if await reject_callback_if_unauthorized(callback_query, settings):
            return

        try:
            _, video_id, step = callback_query.data.split("_", 2)
        except (AttributeError, ValueError):
            await callback_query.answer("Navigation error.", show_alert=True)
            return

        entry = cache.get(video_id)
        if not entry:
            await callback_query.answer(
                "Session expired. Please send the link again.",
                show_alert=True,
            )
            return

        if step not in {"audio", "subtitle", "video"}:
            await callback_query.answer("Navigation expired.", show_alert=True)
            return

        step = _screen_for_step(entry, step)
        await _edit_step_message(callback_query, video_id, entry, step)
        await callback_query.answer()

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

        entry.selected_video_key = format_key
        subtitle_language = _selected_subtitle(entry).language
        selected_audio = _selected_audio(entry)
        audio_format_id = selected_audio.format_id if selected_audio else None
        if selected_audio:
            logger.debug(
                "Starting download with selected audio: format_id=%s language=%s label=%s",
                audio_format_id,
                selected_audio.language,
                _audio_label(selected_audio),
            )
        output_path: Path | None = None
        subtitle_path: Path | None = None
        await callback_query.answer("Starting download...")
        reporter = ProgressReporter(callback_query.message, _title(entry.info))
        await reporter.start("Preparing download...")

        try:
            output_path, subtitle_path = await download_media(
                entry.url,
                video_id,
                format_id,
                settings.download_dir,
                entry.info,
                audio_format_id=audio_format_id,
                progress_hook=_download_progress_hook(
                    reporter,
                    format_id,
                    audio_format_id,
                ),
                cookies_file=settings.cookies_file,
                subtitle_language=subtitle_language,
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

            if subtitle_path and subtitle_path.exists():
                await reporter.done(
                    f"Uploading subtitle `{subtitle_path.name}` "
                    f"({format_bytes(subtitle_path.stat().st_size)})..."
                )
                await client.send_document(
                    chat_id=callback_query.message.chat.id,
                    document=str(subtitle_path),
                    caption=f"**Subtitle:** `{entry.info.get('title')}`",
                    progress=upload_progress,
                )

            await reporter.done("Upload complete.")
            await callback_query.message.delete()
        except Exception as exc:
            await reporter.fail(f"Failed: {exc}")
        finally:
            if output_path and output_path.parent.name == video_id:
                with contextlib.suppress(OSError):
                    shutil.rmtree(output_path.parent)
