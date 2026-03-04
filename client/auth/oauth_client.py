"""OAuth 2.0 PKCE client for Entropia Nexus authentication."""

import base64
import hashlib
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

from ..core.constants import EVENT_AUTH_STATE_CHANGED
from ..core.logger import get_logger
from .models import AuthState, TokenSet
from .token_store import TokenStore

log = get_logger("Auth")

SCOPES = "profile:read skills:read skills:write loadouts:read loadouts:write inventory:read inventory:write notifications:read notifications:write exchange:read exchange:write"
TOKEN_REFRESH_MARGIN_SECONDS = 300  # Refresh 5 min before expiry
CALLBACK_TIMEOUT_SECONDS = 300
DEFAULT_CLIENT_ID = "e5d3b6c4-ec01-468d-b3f2-c0b056cfe47c"


class OAuthClient:
    """Handles OAuth 2.0 PKCE authorization flow with Entropia Nexus."""

    def __init__(self, config, event_bus, token_store: TokenStore):
        self._config = config
        self._event_bus = event_bus
        self._token_store = token_store
        self._tokens: TokenSet | None = None
        self._auth_state = AuthState()
        self._lock = threading.Lock()

        # Restore tokens from disk (fast — no network calls).
        # Network refresh happens later via refresh_in_background().
        self._tokens = self._token_store.load()
        if self._tokens and (not self._tokens.is_expired or self._tokens.refresh_token):
            # Preliminary authenticated state (no username/avatar yet).
            # If access token is expired but refresh token exists,
            # refresh_in_background() will refresh it.
            self._auth_state = AuthState(authenticated=True)

    @property
    def client_id(self) -> str:
        return DEFAULT_CLIENT_ID

    @property
    def auth_state(self) -> AuthState:
        return self._auth_state

    def is_authenticated(self) -> bool:
        return self._auth_state.authenticated

    def get_access_token(self) -> str | None:
        """Get a valid access token, refreshing if needed. Returns None if not authenticated."""
        with self._lock:
            if not self._tokens:
                return None

            if self._tokens.seconds_until_expiry < TOKEN_REFRESH_MARGIN_SECONDS:
                if not self._refresh_token():
                    return None

            return self._tokens.access_token

    def refresh_in_background(self) -> None:
        """Refresh tokens and fetch user info in a background thread.

        Called after the UI is visible so network delays don't block startup.
        """
        def _do_refresh():
            if not self._tokens:
                return
            if self._tokens.is_expired and self._tokens.refresh_token:
                log.info("Access token expired, refreshing via refresh token...")
                if not self._refresh_token():
                    # Refresh failed. If tokens were cleared (auth rejection),
                    # _refresh_token already published unauthenticated state.
                    # If tokens still exist (network error), re-publish so
                    # the UI shows the preliminary authenticated state.
                    if self._tokens:
                        self._update_auth_state(AuthState(authenticated=True))
                    return
            if self._tokens and not self._tokens.is_expired:
                self._refresh_user_info()

        threading.Thread(target=_do_refresh, daemon=True, name="auth-refresh").start()

    def login(self) -> bool | str:
        """Start the OAuth login flow. Opens browser, waits for redirect.

        Returns True on success, or an error message string on failure.
        """
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)

        # Start local callback server
        auth_code = None
        received_state = None
        server_error = None

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self_handler):
                nonlocal auth_code, received_state, server_error
                parsed = urllib.parse.urlparse(self_handler.path)

                # Ignore favicon and other non-callback requests (browser prefetch)
                if parsed.path != "/callback":
                    self_handler.send_response(204)
                    self_handler.end_headers()
                    return

                params = urllib.parse.parse_qs(parsed.query)

                if "error" in params:
                    server_error = params["error"][0]
                    self_handler.send_response(200)
                    self_handler.send_header("Content-Type", "text/html")
                    self_handler.end_headers()
                    self_handler.wfile.write(
                        f"<html><body><h2>Login failed: {server_error}</h2>"
                        f"<p>You can close this tab.</p></body></html>".encode()
                    )
                elif "code" in params:
                    auth_code = params["code"][0]
                    received_state = params.get("state", [None])[0]
                    self_handler.send_response(200)
                    self_handler.send_header("Content-Type", "text/html")
                    self_handler.end_headers()
                    self_handler.wfile.write(
                        b"<html><body><h2>Login successful!</h2>"
                        b"<p>You can close this tab and return to the app.</p></body></html>"
                    )
                else:
                    self_handler.send_response(400)
                    self_handler.end_headers()

            def log_message(self_handler, format, *log_args):
                pass  # Suppress HTTP server logs

        redirect_port = self._config.oauth_redirect_port
        redirect_uri = f"http://127.0.0.1:{redirect_port}/callback"

        try:
            server = HTTPServer(("127.0.0.1", redirect_port), CallbackHandler)
        except OSError as e:
            log.error("Cannot start login server on port %s: %s", redirect_port, e)
            return f"Cannot start login server on port {redirect_port}"

        # Build authorization URL
        auth_url = self._build_auth_url(code_challenge, state, redirect_uri)

        # Open browser
        if webbrowser.open(auth_url):
            log.info("Opened browser for login")
        else:
            log.warning("Could not open browser. Open this URL manually:\n  %s", auth_url)
        log.info("Waiting for login callback on port %s...", redirect_port)

        # Wait for callback — loop to handle spurious requests (favicon, prefetch)
        deadline = time.monotonic() + CALLBACK_TIMEOUT_SECONDS
        while auth_code is None and server_error is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            server.timeout = remaining
            server.handle_request()

        server.server_close()

        # Validate
        if server_error:
            log.error("Login failed: %s", server_error)
            return f"Login failed: {server_error}"

        if not auth_code:
            log.error("Login timed out or no code received")
            return "Login timed out. Please try again."

        if received_state != state:
            log.error("State mismatch — possible CSRF attack")
            return "Login failed: security token mismatch"

        # Exchange code for tokens
        return self._exchange_code(auth_code, code_verifier, redirect_uri)

    def logout(self) -> None:
        """Revoke tokens and clear auth state."""
        if self._tokens:
            try:
                self._revoke_token(self._tokens.access_token)
            except Exception as e:
                log.error("Token revocation failed: %s", e)

        with self._lock:
            self._tokens = None
        self._token_store.clear()
        self._update_auth_state(AuthState())
        log.warning("Logged out")

    def _build_auth_url(self, code_challenge: str, state: str, redirect_uri: str) -> str:
        base_url = self._config.nexus_base_url
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{base_url}/api/oauth/authorize?{urllib.parse.urlencode(params)}"

    def _exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> bool | str:
        """Exchange authorization code for tokens. Returns True or error string."""
        base_url = self._config.nexus_base_url
        try:
            resp = requests.post(f"{base_url}/api/oauth/token", data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }, headers={"Origin": base_url}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            tokens = TokenSet(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=datetime.utcnow() + timedelta(seconds=data["expires_in"]),
                scope=data.get("scope", SCOPES),
            )

            with self._lock:
                self._tokens = tokens
            self._token_store.save(tokens)
            self._refresh_user_info()
            log.warning("Login successful")
            return True

        except requests.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else "(no body)"
            log.error("Token exchange failed: %s — %s", e, body)
            return "Token exchange failed. Please try again."
        except Exception as e:
            log.error("Token exchange failed: %s", e)
            return "Token exchange failed. Please try again."

    def _refresh_token(self) -> bool:
        """Refresh the access token using the refresh token. Returns success."""
        if not self._tokens or not self._tokens.refresh_token:
            return False

        base_url = self._config.nexus_base_url
        try:
            resp = requests.post(f"{base_url}/api/oauth/token", data={
                "grant_type": "refresh_token",
                "refresh_token": self._tokens.refresh_token,
                "client_id": self.client_id,
            }, headers={"Origin": base_url}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            tokens = TokenSet(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=datetime.utcnow() + timedelta(seconds=data["expires_in"]),
                scope=data.get("scope", self._tokens.scope),
            )

            self._tokens = tokens
            self._token_store.save(tokens)
            return True

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (400, 401, 403):
                # Refresh token rejected by server — truly logged out
                log.error("Refresh token rejected (HTTP %d), clearing session", status)
                self._tokens = None
                self._token_store.clear()
                self._update_auth_state(AuthState())
            else:
                # Server error (5xx) — keep tokens, retry later
                log.warning("Token refresh failed (HTTP %d), will retry", status)
            return False
        except Exception as e:
            # Network error (timeout, DNS, connection refused) — keep tokens
            log.warning("Token refresh failed (network): %s", e)
            return False

    def _revoke_token(self, token: str) -> None:
        base_url = self._config.nexus_base_url
        requests.post(f"{base_url}/api/oauth/revoke", data={
            "token": token,
            "client_id": self.client_id,
        }, headers={"Origin": base_url}, timeout=10)

    def _refresh_user_info(self) -> None:
        """Fetch user info and update auth state."""
        token = self.get_access_token()
        if not token:
            return

        base_url = self._config.nexus_base_url
        try:
            resp = requests.get(f"{base_url}/api/oauth/userinfo", headers={
                "Authorization": f"Bearer {token}",
            }, timeout=10)
            resp.raise_for_status()
            user = resp.json()

            state = AuthState(
                authenticated=True,
                username=user.get("username"),
                avatar_url=user.get("avatar"),
                user_id=user.get("id"),
                eu_name=user.get("eu_name"),
                scopes=self._tokens.scope.split() if self._tokens else [],
            )
            self._update_auth_state(state)

        except Exception as e:
            log.error("Failed to fetch user info: %s", e)

    def _update_auth_state(self, state: AuthState) -> None:
        self._auth_state = state
        self._event_bus.publish(EVENT_AUTH_STATE_CHANGED, state)

    @staticmethod
    def _generate_code_verifier() -> str:
        return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
