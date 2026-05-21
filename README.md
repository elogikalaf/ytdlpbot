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
OWNER_ID=111111111, 222222222
DOWNLOAD_DIR=downloads
COOKIES_FILE=
```

`OWNER_ID` is a comma-separated allowlist. The bot silently ignores messages
from users who are not on that list.

`COOKIES_FILE` is optional. Set it to a Netscape-format cookies file when
sites like YouTube require a signed-in browser session:

```sh
yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download "https://www.youtube.com/"
```

Then set:

```sh
COOKIES_FILE=/absolute/path/to/cookies.txt
```

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

Download and upload progress are shown in the Telegram status message.
