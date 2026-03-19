# spot2gram

Sync your currently playing Spotify track to Telegram music status. Uses a Telegram Bot to download track and the Spotify Web API.

> 🇷🇺 README на Русском доступно [здесь](README-RU.md)

Thanks to [@playinnowbot](https://t.me/playinnowbot) Telegram bot for the opportunity to get music from it

NOW as @playinnowbot is closed, whole project is running on the clone: [@gigamusicrobot](https://t.me/gigamusicrobot)

![demo image](.github/images/demo.png)
![demo image 2](.github/images/demo2.png)

## How it works
- Checks if something is playing right now on Spotify
- If something is playing finds track via telegram bot and adds it to your Telegram music status
- Clears previous track when playback stops or track changes

## Requirements
- [Python](https://www.python.org/downloads/) 3.10+
- Spotify Premium [(check here)](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)

## Create a Spotify App
1. Open the Spotify Developer Dashboard (`https://developer.spotify.com/dashboard`)
2. Create an app
3. In app settings add the Redirect URI: `http://127.0.0.1:8888/callback`
4. Save changes
5. Copy your `Client ID` and `Client Secret` and fill them in .env

## Telegram Setup
1.  Start [@gigamusicrobot](https://t.me/gigamusicrobot) Telegram bot
2. Link Spotify account in the bot
3. Create new Telegram Channel that will contain tracks
4. Get ID of telegram channel and fill it in .env (usually ID should start with -100, if ID doesn't - add -100 yourself)

## Quick Start

### Clone and enter the project
```bash
git clone https://github.com/01473/spot2gram.git
cd spot2gram
```

### Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env-example .env
nano .env  # fill SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, CHANNEL_ID

# Get refresh token
python3 spotify_auth.py

nano .env # fill SPOTIFY_REFRESH_TOKEN you just got from script

# Run
python3 main.py
```

### Windows (PowerShell)
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env-example .env
# open .env and fill SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, CHANNEL_ID

# Get refresh token
python spotify_auth.py

# open .env again and fill SPOTIFY_REFRESH_TOKEN you just got from script

# Run
python main.py
```

## Configure .env
Copy `.env-example` to `.env` and fill the values:
```ini
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REFRESH_TOKEN=  # should be filled after running spotify_auth.py
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
CHANNEL_ID=your_telegram_channel_id
POLL_INTERVAL_SECONDS=5
```

## Environment Variables
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`: from your Spotify app
- `SPOTIFY_REFRESH_TOKEN`: obtained via `spotify_auth.py`
- `SPOTIFY_REDIRECT_URI`: default `http://127.0.0.1:8888/callback`
- `CHANNEL_ID`: numeric chat/channel ID to post the inline result (can be your Saved Messages or a private channel, better private channel)
- `POLL_INTERVAL_SECONDS`: Spotify polling interval in seconds

> [!NOTE]
> If no spotify refresh token is returned, revoke the app in your Spotify account (Apps) and run auth again.
> Keep your Redirect URI exactly `http://127.0.0.1:8888/callback` in both your app settings and `.env`.
