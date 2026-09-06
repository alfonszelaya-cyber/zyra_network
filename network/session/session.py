"""
Production network session lifecycle.

Session identity is network-level state. Authentication and
authorization remain owned by Protocol/Security.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic
from uuid import uuid4


class SessionState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass(slots=True)
class NetworkSession:
    session_id: str
    peer_id: str
    state: SessionState = SessionState.NEW
    created_at: float = field(
        default_factory=monotonic
    )
    last_activity: float = field(
        default_factory=monotonic
    )
    metadata: dict[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.session_id = self.session_id.strip()
        self.peer_id = self.peer_id.strip()

        if not self.session_id:
            raise ValueError(
                "session_id cannot be empty"
            )

        if not self.peer_id:
            raise ValueError(
                "peer_id cannot be empty"
            )


class SessionManager:
    """Thread-safe network session registry."""

    def __init__(
        self,
        *,
        idle_timeout_seconds: float = 900.0,
    ) -> None:

        if idle_timeout_seconds <= 0:
            raise ValueError(
                "idle timeout must be positive"
            )

        self._idle_timeout = (
            idle_timeout_seconds
        )

        self._sessions: dict[
            str,
            NetworkSession,
        ] = {}

        self._lock = RLock()

    def create(
        self,
        peer_id: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> NetworkSession:

        session = NetworkSession(
            session_id=str(
                uuid4()
            ),
            peer_id=peer_id,
            state=SessionState.ACTIVE,
            metadata=dict(
                metadata or {}
            ),
        )

        with self._lock:
            self._sessions[
                session.session_id
            ] = session

        return session

    def get(
        self,
        session_id: str,
    ) -> NetworkSession | None:

        with self._lock:
            return self._sessions.get(
                session_id.strip()
            )

    def touch(
        self,
        session_id: str,
    ) -> NetworkSession:

        with self._lock:
            session = self._sessions.get(
                session_id.strip()
            )

            if session is None:
                raise LookupError(
                    f"session not found: "
                    f"{session_id}"
                )

            if session.state not in {
                SessionState.ACTIVE,
                SessionState.DRAINING,
            }:
                raise ValueError(
                    "session is not active"
                )

            session.last_activity = monotonic()

            return session

    def set_state(
        self,
        session_id: str,
        state: SessionState,
    ) -> NetworkSession:

        if not isinstance(
            state,
            SessionState,
        ):
            raise TypeError(
                "state must be SessionState"
            )

        with self._lock:
            session = self._sessions.get(
                session_id.strip()
            )

            if session is None:
                raise LookupError(
                    f"session not found: "
                    f"{session_id}"
                )

            session.state = state
            session.last_activity = monotonic()

            return session

    def expire_idle(
        self,
        *,
        now: float | None = None,
    ) -> tuple[str, ...]:

        current = (
            monotonic()
            if now is None
            else now
        )

        expired: list[str] = []

        with self._lock:
            for session in (
                self._sessions.values()
            ):
                if session.state not in {
                    SessionState.ACTIVE,
                    SessionState.DRAINING,
                }:
                    continue

                idle = (
                    current
                    - session.last_activity
                )

                if idle >= self._idle_timeout:
                    session.state = (
                        SessionState.EXPIRED
                    )

                    expired.append(
                        session.session_id
                    )

        return tuple(expired)

    def close(
        self,
        session_id: str,
    ) -> bool:

        with self._lock:
            session = self._sessions.get(
                session_id.strip()
            )

            if session is None:
                return False

            session.state = (
                SessionState.CLOSED
            )

            session.last_activity = monotonic()

            return True

    def snapshot(
        self,
    ) -> tuple[NetworkSession, ...]:

        with self._lock:
            return tuple(
                NetworkSession(
                    session_id=item.session_id,
                    peer_id=item.peer_id,
                    state=item.state,
                    created_at=item.created_at,
                    last_activity=item.last_activity,
                    metadata=dict(
                        item.metadata
                    ),
                )
                for item
                in self._sessions.values()
            )


__all__ = [
    "SessionState",
    "NetworkSession",
    "SessionManager",
]
