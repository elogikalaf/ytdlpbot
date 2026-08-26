# ytdlpbot

A small private Telegram bot that downloads video or MP3 audio through `yt-dlp`
and uploads it back to allowed Telegram users.

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

For YouTube downloads, the VPS must also have a JavaScript runtime available to
yt-dlp. Without this, YouTube may return only storyboard/images and yt-dlp will
print `n challenge solving failed`.

The bot now selects audio tracks explicitly by yt-dlp `format_id`. This is
needed for multilingual YouTube videos, where original, dubbed, and generated
audio may all exist on the same video and `bestaudio` can pick the wrong
language.

Recommended VPS setup:

```sh
python -m pip install -U "yt-dlp[default]>=2026.8.19"
sudo apt-get update
sudo apt-get install -y nodejs
```

yt-dlp 2026.08.19 or newer is required for TikTok's current webpage format.
After upgrading an existing installation, restart the bot process so it loads
the new Python package.

```sh
python main.py
```

The bot creates local download files temporarily under `downloads/` and removes
them after upload. The final quality screen includes an `Audio MP3` choice when
yt-dlp reports audio streams for the link.

Download and upload progress are shown in the Telegram status message.
