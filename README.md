# ytdlpbot

A small private Telegram bot that downloads media through `yt-dlp` and uploads it
back to allowed Telegram users.

## Configuration

Set these environment variables before starting the bot:

```sh
cp .env.example .env
```

Then edit `.env`:

```sh
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
ALLOWED_USER_IDS=111111111,222222222
DOWNLOAD_DIR=downloads
```

`ALLOWED_USER_IDS` is a comma-separated allowlist. The bot silently ignores
messages from users who are not on that list.

## Run

Install dependencies first:

```sh
pip install -r requirements.txt
```

```sh
python main.py
```

The bot creates local download files temporarily under `downloads/` and removes
them after upload.
