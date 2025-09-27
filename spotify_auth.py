import os
import base64
import threading
import urllib.parse
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import requests
from dotenv import load_dotenv


def build_authorize_url(client_id: str, redirect_uri: str, scope: str, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "show_dialog": "true",
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Optional[dict]:
    token_url = "https://accounts.spotify.com/api/token"
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    try:
        resp = requests.post(token_url, headers=headers, data=data, timeout=20)
        if resp.status_code != 200:
            print(f"[spotify] token exchange failed: {resp.status_code} {resp.text}")
            return None
        return resp.json()
    except Exception as exc:
        print(f"[spotify] token exchange error: {exc}")
        return None


def main():
    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()

    if not client_id or not client_secret:
        print("[spotify] Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env")
        return

    print("[info] Ensure this Redirect URI is added in your Spotify App settings:")
    print(f"       {redirect_uri}")

    state = secrets.token_urlsafe(16)
    scope = " ".join([
        "user-read-currently-playing",
        "user-read-playback-state",
    ])

    received = {"code": None, "state": None, "error": None}
    got_code_event = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != urllib.parse.urlparse(redirect_uri).path:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found")
                    return

                qs = urllib.parse.parse_qs(parsed.query)
                code = (qs.get("code") or [None])[0]
                st = (qs.get("state") or [None])[0]
                err = (qs.get("error") or [None])[0]

                received["code"] = code
                received["state"] = st
                received["error"] = err
                got_code_event.set()

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if err:
                    self.wfile.write(b"<h1>Authorization failed</h1>")
                    self.wfile.write(err.encode())
                else:
                    self.wfile.write(b"<h1>Authorization successful</h1>")
                    self.wfile.write(b"You can close this tab and return to the console.")
            except Exception as exc:
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
                print(f"[server] handler error: {exc}")

        def log_message(self, format, *args):
            return

    host, port = urllib.parse.urlparse(redirect_uri).hostname or "127.0.0.1", urllib.parse.urlparse(redirect_uri).port or 8888
    httpd = HTTPServer((host, port), CallbackHandler)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    auth_url = build_authorize_url(client_id, redirect_uri, scope, state)
    print("[action] Open this URL to authorize:")
    print(auth_url)

    try:
        import webbrowser
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("[wait] Waiting for the browser callback...")
    got = got_code_event.wait(timeout=300)
    httpd.shutdown()

    if not got:
        print("[spotify] Timed out waiting for authorization. Try again.")
        return

    if received["error"]:
        print(f"[spotify] Authorization error: {received['error']}")
        return

    if received["state"] != state:
        print("[spotify] Invalid state received. Aborting.")
        return

    if not received["code"]:
        print("[spotify] No authorization code received.")
        return

    tokens = exchange_code_for_tokens(client_id, client_secret, received["code"], redirect_uri)
    if not tokens:
        return

    refresh_token = tokens.get("refresh_token")

    if refresh_token:
        print("\n=== SPOTIFY_REFRESH_TOKEN ===")
        print(refresh_token)
        print("============================\n")
    else:
        print("[spotify] No refresh_token returned. If you previously authorized, remove the app access and try again.")


if __name__ == "__main__":
    main()


