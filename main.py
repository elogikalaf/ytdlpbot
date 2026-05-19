from pyrogram import Client

from ytdlpbot.cache import VideoCache
from ytdlpbot.config import load_settings
from ytdlpbot.handlers import register_handlers


def create_app() -> Client:
    settings = load_settings()
    app = Client(
        "ytdl_bot",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
    )
    register_handlers(app, settings, VideoCache())
    return app


if __name__ == "__main__":
    print("Bot is starting...")
    create_app().run()

