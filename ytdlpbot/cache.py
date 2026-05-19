from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class VideoEntry:
    info: Dict[str, Any]
    url: str
    formats: Dict[str, str] = field(default_factory=dict)


class VideoCache:
    def __init__(self) -> None:
        self._items: Dict[str, VideoEntry] = {}

    def set(self, video_id: str, entry: VideoEntry) -> None:
        self._items[video_id] = entry

    def get(self, video_id: str) -> Optional[VideoEntry]:
        return self._items.get(video_id)

