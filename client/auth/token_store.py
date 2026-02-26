"""Secure token persistence using the OS credential store."""

import json
from datetime import datetime

from .models import TokenSet

SERVICE_NAME = "EntropiaNexusClient"
TOKEN_KEY = "oauth_tokens"


class TokenStore:
    """Store and retrieve OAuth tokens securely via keyring (Windows Credential Manager)."""

    def save(self, tokens: TokenSet) -> None:
        """Persist tokens to the OS credential store."""
        import keyring
        data = json.dumps({
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at.isoformat(),
            "scope": tokens.scope,
        })
        keyring.set_password(SERVICE_NAME, TOKEN_KEY, data)

    def load(self) -> TokenSet | None:
        """Load tokens from the OS credential store. Returns None if not found."""
        import keyring
        data = keyring.get_password(SERVICE_NAME, TOKEN_KEY)
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
        import keyring
        try:
            keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
        except keyring.errors.PasswordDeleteError:
            pass
