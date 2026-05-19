from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    allowed_user_ids: frozenset[int]
    download_dir: str = "downloads"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_allowed_user_ids(raw_value: str) -> frozenset[int]:
    try:
        user_ids = frozenset(
            int(value.strip()) for value in raw_value.split(",") if value.strip()
        )
    except ValueError as exc:
        raise RuntimeError("ALLOWED_USER_IDS must be comma-separated numeric user IDs") from exc

    if not user_ids:
        raise RuntimeError("ALLOWED_USER_IDS must contain at least one Telegram user ID")

    return user_ids


def load_settings() -> Settings:
    load_dotenv()

    try:
        api_id = int(_required_env("API_ID"))
    except ValueError as exc:
        raise RuntimeError("API_ID must be numeric") from exc

    owner_ids = os.getenv("OWNER_ID") or os.getenv("ALLOWED_USER_IDS")
    if not owner_ids:
        raise RuntimeError("Missing required environment variable: OWNER_ID")

    return Settings(
        api_id=api_id,
        api_hash=_required_env("API_HASH"),
        bot_token=_required_env("BOT_TOKEN"),
        allowed_user_ids=_parse_allowed_user_ids(owner_ids),
        download_dir=os.getenv("DOWNLOAD_DIR", "downloads"),
    )
