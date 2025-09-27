from pyrogram import Client
from pyrogram.raw.types import InputDocument
from pyrogram.raw import functions
from pyrogram.file_id import FileId
import asyncio
import os
import base64
import json
import time
from typing import Optional, Tuple
from dotenv import load_dotenv
import requests
load_dotenv()


SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
TARGET_CHANNEL_ID = os.getenv("CHANNEL_ID", "")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "5"))

cached_access_token: Optional[str] = None
access_token_expires_at: float = 0.0

async def refresh_spotify_access_token() -> Optional[str]:
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and SPOTIFY_REFRESH_TOKEN):
        print("[spotify] hey! we are missing env vars, please fill them")
        return None

    global cached_access_token, access_token_expires_at
    if cached_access_token and time.time() < access_token_expires_at - 60:
        return cached_access_token

    def _request_token() -> Optional[dict]:
        import requests

        token_url = "https://accounts.spotify.com/api/token"
        basic = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        headers = {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "refresh_token", "refresh_token": SPOTIFY_REFRESH_TOKEN}
        try:
            resp = requests.post(token_url, headers=headers, data=data, timeout=15)
            if resp.status_code != 200:
                print(f"[spotify] token refresh failed: {resp.status_code} {resp.text}")
                return None
            return resp.json()
        except Exception as exc:
            print(f"[spotify] token refresh error: {exc}")
            return None

    payload = await asyncio.to_thread(_request_token)
    if not payload:
        return None

    token = payload.get("access_token")
    if not token:
        return None

    expires_in = int(payload.get("expires_in", 3600))
    cached_access_token = token
    access_token_expires_at = time.time() + max(expires_in - 30, 0)
    return token


async def fetch_currently_playing(access_token: str) -> Optional[Tuple[str, str]]:
    def _request_now_playing() -> Optional[Tuple[str, str]]:

        url = "https://api.spotify.com/v1/me/player/currently-playing"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 204:
                return None
            if resp.status_code != 200:
                print(f"[spotify] currently playing failed: {resp.status_code} {resp.text}")
                return None
            payload = resp.json()
            is_playing = payload.get("is_playing", False)
            if not is_playing:
                return None
            item = payload.get("item") or {}
            track_id = item.get("id")
            track_name = item.get("name") or ""
            artists = item.get("artists") or []
            artist_names = ", ".join(a.get("name") for a in artists if a and a.get("name"))
            if not (track_id and track_name and artist_names):
                return None
            query_text = f"{artist_names} - {track_name}"
            return track_id, query_text
        except Exception as exc:
            print(f"[spotify] currently playing error: {exc}")
            return None

    return await asyncio.to_thread(_request_now_playing)


async def send_inline_top_result_and_get_message(app: Client, query_text: str):
    try:
        results = await app.get_inline_bot_results("@playinnowbot", query_text)
        if not results or not results.results:
            print(f"[tg] no inline results for: {query_text}")
            return None
        top = results.results[0]
        sent = await app.send_inline_bot_result(TARGET_CHANNEL_ID, results.query_id, top.id)
        if sent:
            message = sent
        else:
            print("[tg] using fallback get_chat_history")
            async for m in app.get_chat_history(TARGET_CHANNEL_ID, limit=1):
                message = m
                break
        return message
    except Exception as exc:
        print(f"[tg] inline send error: {exc}")
        return None


def build_input_document_from_message_audio(message) -> Optional[InputDocument]:
    try:
        if not message or not getattr(message, "audio", None):
            return None
        fileid = message.audio.file_id
        decoded = FileId.decode(fileid)
        return InputDocument(id=decoded.media_id, access_hash=decoded.access_hash, file_reference=decoded.file_reference)
    except Exception as exc:
        print(f"[tg] fileid decode error: {exc}")
        return None


async def save_music(app: Client, input_document: InputDocument) -> bool:
    try:
        r = await app.invoke(functions.account.SaveMusic(id=input_document))
        return bool(r)
    except Exception as exc:
        print(f"[tg] save music error: {exc}")
        return False


async def unsave_music(app: Client, input_document: InputDocument) -> bool:
    try:
        r = await app.invoke(functions.account.SaveMusic(id=input_document, unsave=True))
        return bool(r)
    except Exception as exc:
        print(f"[tg] unsave music error: {exc}")
        return False


def has_downloading_button(message) -> bool:
    try:
        markup = getattr(message, "reply_markup", None)
        keyboard = getattr(markup, "inline_keyboard", None)
        if not keyboard:
            return False
        for row in keyboard:
            for btn in row:
                text = getattr(btn, "text", "") or ""
                if "downloading" in text.lower():
                    return True
        return False
    except Exception:
        return False


async def wait_for_audio_ready(app: Client, chat_id: int, message_id: int, poll_seconds: float = 1.0):
    try:
        attempts = 20
        for _ in range(max(attempts, 1)):
            msg = await app.get_messages(chat_id, message_id)
            if getattr(msg, "audio", None) and not has_downloading_button(msg):
                return msg
            await asyncio.sleep(poll_seconds)
        return await app.get_messages(chat_id, message_id)
    except Exception as exc:
        print(f"[tg] wait_for_audio_ready error: {exc}")
        return None

async def main():
    last_spotify_track_id: Optional[str] = None
    last_saved_input_document: Optional[InputDocument] = None

    async with Client("music_sync", fetch_topics=False, skip_updates=True, no_updates=True, api_id=2040, api_hash="b18441a1ff607e10a989891a5462e627", app_version="6.1.3 x64", device_model="Z690-c/ac", system_version="Windows 10 x64", lang_code="ru", system_lang_code="ru") as app:
        print("starting music sync")
        while True:
            try:
                access_token = await refresh_spotify_access_token()
                if not access_token:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                now_playing = await fetch_currently_playing(access_token)
                if not now_playing:
                    # Nothing playing -> cleanup if needed
                    if last_spotify_track_id is not None:
                        await unsave_music(app, last_saved_input_document)
                        last_spotify_track_id = None
                        last_saved_input_document = None
                        print("[state] music stopped, cleaned up")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                track_id, query_text = now_playing
                if track_id == last_spotify_track_id:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue
                if last_spotify_track_id is not None:
                    await unsave_music(app, last_saved_input_document)

                message = await send_inline_top_result_and_get_message(app, query_text)
                if not message:
                    print(f"[tg] failed to send inline for: {query_text}")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                message = await wait_for_audio_ready(app, TARGET_CHANNEL_ID, message.id)
                if not message:
                    print("[tg] message not found after sending, skipping")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                input_document = build_input_document_from_message_audio(message)
                if not input_document:
                    print("[tg] sent message has no audio to save, skipping save music")
                    last_spotify_track_id = track_id
                    last_saved_input_document = None
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                ok = await save_music(app, input_document)
                if ok:
                    print(f"[state] saved to profile: {query_text}")
                else:
                    print(f"[state] save failed for: {query_text}")

                last_spotify_track_id = track_id
                last_saved_input_document = input_document

                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except Exception as loop_exc:
                print(f"[runner] loop error: {loop_exc}")
                await asyncio.sleep(10)


asyncio.run(main())