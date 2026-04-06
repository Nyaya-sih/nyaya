"""In-memory session store for legal assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional
from uuid import uuid4


@dataclass
class SessionTurn:
    """Single conversation turn."""

    role: str
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StoredSession:
    """Stored session context and messages."""

    session_id: str
    created_at: datetime
    expires_at: datetime
    context_source: str = "none"
    context_source_ref: Optional[str] = None
    context_title: Optional[str] = None
    context_text: str = ""
    messages: list[SessionTurn] = field(default_factory=list)


class InMemorySessionStore:
    """Thread-safe in-memory session store with TTL cleanup."""

    def __init__(self, ttl_minutes: int, max_turns: int):
        self._ttl_minutes = ttl_minutes
        self._max_turns = max_turns
        self._sessions: dict[str, StoredSession] = {}
        self._lock = Lock()

    def create_session(self) -> StoredSession:
        """Create and return a new session."""
        now = datetime.now(timezone.utc)
        session_id = f"asst_{uuid4().hex}"
        session = StoredSession(
            session_id=session_id,
            created_at=now,
            expires_at=now + timedelta(minutes=self._ttl_minutes),
        )
        with self._lock:
            self._cleanup_locked(now)
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[StoredSession]:
        """Get session by ID if valid and unexpired."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete session by ID."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def update_context(
        self,
        session_id: str,
        source: str,
        source_ref: Optional[str],
        title: Optional[str],
        text: str,
    ) -> Optional[StoredSession]:
        """Update session context and return updated session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.context_source = source
            session.context_source_ref = source_ref
            session.context_title = title
            session.context_text = text
            return session

    def append_message(
        self, session_id: str, role: str, content: str
    ) -> Optional[StoredSession]:
        """Append message to session history and cap history length."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.messages.append(SessionTurn(role=role, content=content))
            if len(session.messages) > self._max_turns:
                session.messages = session.messages[-self._max_turns :]
            return session

    def _cleanup_locked(self, now: datetime) -> None:
        """Remove expired sessions. Caller must hold lock."""
        expired_ids = [
            sid for sid, session in self._sessions.items() if session.expires_at <= now
        ]
        for sid in expired_ids:
            self._sessions.pop(sid, None)
