"""Secure token persistence using the OS credential store.

Falls back to a plaintext JSON file on Linux when D-Bus SecretService
is unavailable (e.g. no GNOME Keyring / KWallet).
"""

import json
import os
import platform
from datetime import datetime

import keyring

from ..core.logger import get_logger
from .models import TokenSet

log = get_logger("TokenStore")

SERVICE_NAME = "EntropiaNexusClient"
TOKEN_KEY = "oauth_tokens"
_TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".entropia-nexus", "tokens.json")

# PyInstaller strips dist-info metadata, so keyring can't discover backends
# via entry_points.  Set the backend explicitly for each platform.
_keyring_available = True

if platform.system() == "Windows":
    from keyring.backends.Windows import WinVaultKeyring
    keyring.set_keyring(WinVaultKeyring())
else:
    try:
        from keyring.backends.SecretService import Keyring as SecretServiceKeyring
        keyring.set_keyring(SecretServiceKeyring())
    except Exception:
        _keyring_available = False
        log.warning(
            "Secure keyring unavailable (no D-Bus SecretService) "
            "— tokens will be stored in plaintext at %s",
            _TOKEN_FILE,
        )


class TokenStore:
    """Store and retrieve OAuth tokens via OS keyring, with file fallback."""

    def save(self, tokens: TokenSet) -> None:
        """Persist tokens to the OS credential store (or fallback file)."""
        data = json.dumps({
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at.isoformat(),
            "scope": tokens.scope,
        })
        if _keyring_available:
            keyring.set_password(SERVICE_NAME, TOKEN_KEY, data)
        else:
            self._write_file(data)

    def load(self) -> TokenSet | None:
        """Load tokens from the OS credential store (or fallback file)."""
        data = (keyring.get_password(SERVICE_NAME, TOKEN_KEY)
                if _keyring_available else self._read_file())
        if not data:
            return None
        try:
            parsed = json.loads(data)
            return TokenSet(
                access_token=parsed["access_token"],
                refresh_token=parsed["refresh_token"],
                expires_at=datetime.fromisoformat(parsed["expires_at"]),
                scope=parsed.get("scope", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def clear(self) -> None:
        """Remove stored tokens."""
        if _keyring_available:
            try:
                keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
            except keyring.errors.PasswordDeleteError:
                pass
        else:
            self._remove_file()

    # --- File-based fallback (Linux without SecretService) ---

    @staticmethod
    def _write_file(data: str) -> None:
        try:
            os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
            fd = os.open(_TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(data)
        except OSError as e:
            log.error("Failed to write token file: %s", e)

    @staticmethod
    def _read_file() -> str | None:
        try:
            with open(_TOKEN_FILE) as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def _remove_file() -> None:
        try:
            os.remove(_TOKEN_FILE)
        except OSError:
            pass
