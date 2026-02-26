"""Authentication data models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TokenSet:
    """OAuth token pair with metadata."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str = ""

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @property
    def seconds_until_expiry(self) -> float:
        return (self.expires_at - datetime.utcnow()).total_seconds()


@dataclass
class AuthState:
    """Current authentication state, published via EventBus."""
    authenticated: bool = False
    username: str | None = None
    avatar_url: str | None = None
    user_id: int | None = None
    scopes: list[str] = field(default_factory=list)
