from __future__ import annotations

from typing import Optional

from pyrogram.types import CallbackQuery, Message

from ytdlpbot.config import Settings


def is_allowed_user(user_id: Optional[int], settings: Settings) -> bool:
    return user_id is not None and user_id in settings.allowed_user_ids


async def reject_message_if_unauthorized(message: Message, settings: Settings) -> bool:
    user_id = message.from_user.id if message.from_user else None
    return not is_allowed_user(user_id, settings)


async def reject_callback_if_unauthorized(
    callback_query: CallbackQuery, settings: Settings
) -> bool:
    user_id = callback_query.from_user.id if callback_query.from_user else None
    if is_allowed_user(user_id, settings):
        return False

    await callback_query.answer("Not authorized.", show_alert=True)
    return True

