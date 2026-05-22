from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SubtitleChoice:
    language: Optional[str]
    label: str
    source: str


@dataclass
class AudioTrack:
    format_id: str
    language: Optional[str]
    language_display: str
    is_default: bool
    is_original: bool
    is_audio_only: bool
    abr: Optional[float]
    source_preference: Optional[int]
    language_preference: Optional[int]
    format_note: Optional[str]


@dataclass
class VideoEntry:
    info: Dict[str, Any]
    url: str
    formats: Dict[str, str] = field(default_factory=dict)
    audio_tracks: Dict[str, AudioTrack] = field(default_factory=dict)
    subtitles: Dict[str, SubtitleChoice] = field(default_factory=dict)
    selected_video_key: Optional[str] = None
    selected_audio_key: Optional[str] = None
    selected_subtitle_key: str = "none"
    current_step: str = "audio"


class VideoCache:
    def __init__(self) -> None:
        self._items: Dict[str, VideoEntry] = {}

    def set(self, video_id: str, entry: VideoEntry) -> None:
        self._items[video_id] = entry

    def get(self, video_id: str) -> Optional[VideoEntry]:
        return self._items.get(video_id)
