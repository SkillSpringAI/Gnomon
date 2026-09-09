"""Ephemeral local provider credential sessions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import RLock


@dataclass
class _Session:
    token: str
    expires_at: datetime


class ProviderSessionStore:
    """Keep one-time provider credentials in process memory only."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = RLock()

    def create(self, token: str, ttl_seconds: int) -> tuple[str, datetime]:
        session_id = token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        with self._lock:
            self._sessions[session_id] = _Session(token=token, expires_at=expires_at)
        return session_id, expires_at

    def get(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expires_at <= datetime.now(UTC):
                self._sessions.pop(session_id, None)
                return None
            return session.token

    def delete(self, session_id: str | None) -> None:
        if session_id:
            with self._lock:
                self._sessions.pop(session_id, None)
