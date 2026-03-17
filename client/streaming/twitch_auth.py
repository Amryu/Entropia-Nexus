"""Twitch OAuth — implicit grant flow for chat authentication.

Opens the system browser for Twitch login, catches the token via a
localhost HTTP server.  The token is stored in the OS keyring via the
existing TokenStore infrastructure.
"""

from __future__ import annotations

import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from ..core.logger import get_logger

log = get_logger("TwitchAuth")

DEFAULT_TWITCH_CLIENT_ID = "0jdvickf4cpdz3uc5cgxjltp4mll7q"

# Reuse the keyring instance from the existing token store — it handles
# PyInstaller backend setup (WinVaultKeyring on Windows, SecretService
# on Linux).  Importing token_store triggers the backend configuration.
_TWITCH_TOKEN_KEY = "twitch_oauth_token"
_DISPLAY_NAME_KEY = "twitch_display_name"
_CHAT_COLOR_KEY = "twitch_chat_color"


def _keyring():
    """Return the configured keyring module (lazy import to avoid circular deps)."""
    from ..auth.token_store import keyring as _kr, SERVICE_NAME  # noqa: F401
    return _kr, SERVICE_NAME


def load_twitch_token() -> str:
    """Load the Twitch OAuth token from the OS keyring."""
    try:
        kr, svc = _keyring()
        token = kr.get_password(svc, _TWITCH_TOKEN_KEY)
        return token or ""
    except Exception:
        return ""


def save_twitch_token(token: str) -> None:
    """Save the Twitch OAuth token to the OS keyring."""
    try:
        kr, svc = _keyring()
        if token:
            kr.set_password(svc, _TWITCH_TOKEN_KEY, token)
        else:
            kr.delete_password(svc, _TWITCH_TOKEN_KEY)
    except Exception as exc:
        log.warning("Failed to save Twitch token to keyring: %s", exc)


def load_twitch_display_name() -> str:
    """Load the cached Twitch display name from keyring."""
    try:
        kr, svc = _keyring()
        name = kr.get_password(svc, _DISPLAY_NAME_KEY)
        return name or ""
    except Exception:
        return ""


def save_twitch_display_name(name: str) -> None:
    """Cache the Twitch display name in keyring."""
    try:
        kr, svc = _keyring()
        if name:
            kr.set_password(svc, _DISPLAY_NAME_KEY, name)
    except Exception:
        pass


def load_twitch_chat_color() -> str:
    """Load the cached Twitch chat color from keyring."""
    try:
        kr, svc = _keyring()
        color = kr.get_password(svc, _CHAT_COLOR_KEY)
        return color or ""
    except Exception:
        return ""


def save_twitch_chat_color(color: str) -> None:
    """Cache the Twitch chat color in keyring."""
    try:
        kr, svc = _keyring()
        if color:
            kr.set_password(svc, _CHAT_COLOR_KEY, color)
    except Exception:
        pass


def fetch_twitch_user_info(token: str, client_id: str) -> dict:
    """Fetch the authenticated user's display name and chat color.

    Call from a background thread.
    Returns ``{"display_name": str, "color": str}``.
    """
    import requests
    headers = {"Authorization": f"Bearer {token}", "Client-Id": client_id}
    result = {"display_name": "", "color": ""}
    try:
        resp = requests.get(
            "https://api.twitch.tv/helix/users",
            headers=headers, timeout=10,
        )
        if resp.ok:
            data = resp.json().get("data", [])
            if data:
                result["display_name"] = data[0].get("display_name", "")
                user_id = data[0].get("id", "")
                # Fetch chat color
                if user_id:
                    color_resp = requests.get(
                        f"https://api.twitch.tv/helix/chat/color?user_id={user_id}",
                        headers=headers, timeout=10,
                    )
                    if color_resp.ok:
                        color_data = color_resp.json().get("data", [])
                        if color_data:
                            result["color"] = color_data[0].get("color", "")
    except Exception as exc:
        log.debug("Failed to fetch Twitch user info: %s", exc)
    return result


def fetch_twitch_display_name(token: str, client_id: str) -> str:
    """Fetch display name only (backward compat)."""
    return fetch_twitch_user_info(token, client_id).get("display_name", "")


_REDIRECT_PORT = 47833  # different from Nexus OAuth port (47832)
_REDIRECT_URI = f"http://localhost:{_REDIRECT_PORT}"
_SCOPES = "chat:read chat:edit"

# HTML page served at redirect URI.  Twitch implicit grant puts the
# token in the URL fragment (#), which the browser doesn't send to the
# server.  This page reads the fragment via JS and sends it back.
_CALLBACK_HTML = """<!DOCTYPE html>
<html><head><title>Twitch Login</title>
<style>
  body { background: #18181b; color: #efeff1; font-family: sans-serif;
         display: flex; justify-content: center; align-items: center;
         height: 100vh; margin: 0; }
  .box { text-align: center; }
  h2 { color: #9147ff; }
</style></head>
<body><div class="box">
  <h2>Twitch Connected!</h2>
  <p id="msg">Authenticating...</p>
</div>
<script>
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  const token = params.get('access_token');
  if (token) {
    fetch('/token?access_token=' + token).then(() => {
      document.getElementById('msg').textContent =
        'You can close this tab and return to the app.';
    });
  } else {
    document.getElementById('msg').textContent =
      'Authentication failed — no token received.';
  }
</script></body></html>"""

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><title>Done</title></head>
<body><script>window.close()</script></body></html>"""


def twitch_login(client_id: str) -> str | None:
    """Run the Twitch OAuth implicit grant flow.

    Opens the system browser for Twitch login.  Blocks until the user
    completes login or the timeout expires (120 s).

    Args:
        client_id: Twitch application Client ID.

    Returns:
        The OAuth access token, or None on failure/cancel.
    """
    if not client_id:
        log.error("No Twitch Client ID configured")
        return None

    result = {"token": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/token":
                # JS callback with the token
                qs = parse_qs(parsed.query)
                token = qs.get("access_token", [None])[0]
                if token:
                    result["token"] = token
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_SUCCESS_HTML.encode())
                return

            # Serve the callback page (reads fragment via JS)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_CALLBACK_HTML.encode())

        def log_message(self, fmt, *args):
            pass  # suppress server logs

    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={_REDIRECT_URI}"
        f"&response_type=token"
        f"&scope={_SCOPES.replace(' ', '+')}"
    )

    try:
        server = HTTPServer(("127.0.0.1", _REDIRECT_PORT), Handler)
        server.timeout = 120

        webbrowser.open(auth_url)
        log.info("Opened Twitch login in browser")

        # Handle two requests: the redirect page + the JS token callback
        server.handle_request()  # serves the HTML page
        if result["token"] is None:
            server.handle_request()  # receives the token via /token?...

        server.server_close()
    except Exception as exc:
        log.error("Twitch login failed: %s", exc)
        return None

    if result["token"]:
        log.info("Twitch login successful")
    else:
        log.warning("Twitch login: no token received")

    return result["token"]
