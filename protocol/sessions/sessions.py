from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from uuid import UUID, uuid4


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class ProtocolSession:
    session_id: UUID
    local_identity: str
    remote_identity: str
    state: SessionState
    created_at: datetime
    activated_at: datetime | None = None
    closed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        local_identity: str,
        remote_identity: str,
    ) -> "ProtocolSession":

        local_identity = local_identity.strip()
        remote_identity = remote_identity.strip()

        if not local_identity:
            raise ValueError(
                "local_identity cannot be empty"
            )

        if not remote_identity:
            raise ValueError(
                "remote_identity cannot be empty"
            )

        return cls(
            session_id=uuid4(),
            local_identity=local_identity,
            remote_identity=remote_identity,
            state=SessionState.CREATED,
            created_at=datetime.now(
                timezone.utc
            ),
        )


class SessionManager:

    def __init__(self) -> None:
        self._sessions: dict[
            UUID,
            ProtocolSession,
        ] = {}

        self._lock = RLock()

    def create(
        self,
        local_identity: str,
        remote_identity: str,
    ) -> ProtocolSession:

        session = ProtocolSession.create(
            local_identity,
            remote_identity,
        )

        with self._lock:
            self._sessions[
                session.session_id
            ] = session

        return session

    def activate(
        self,
        session_id: UUID,
    ) -> ProtocolSession:

        with self._lock:
            session = self._get(session_id)

            if session.state is SessionState.CLOSED:
                raise RuntimeError(
                    "Closed session cannot be activated"
                )

            if session.state is SessionState.ACTIVE:
                return session

            updated = ProtocolSession(
                session_id=session.session_id,
                local_identity=session.local_identity,
                remote_identity=session.remote_identity,
                state=SessionState.ACTIVE,
                created_at=session.created_at,
                activated_at=datetime.now(
                    timezone.utc
                ),
                closed_at=None,
            )

            self._sessions[
                session_id
            ] = updated

            return updated

    def close(
        self,
        session_id: UUID,
    ) -> ProtocolSession:

        with self._lock:
            session = self._get(session_id)

            if session.state is SessionState.CLOSED:
                return session

            updated = ProtocolSession(
                session_id=session.session_id,
                local_identity=session.local_identity,
                remote_identity=session.remote_identity,
                state=SessionState.CLOSED,
                created_at=session.created_at,
                activated_at=session.activated_at,
                closed_at=datetime.now(
                    timezone.utc
                ),
            )

            self._sessions[
                session_id
            ] = updated

            return updated

    def get(
        self,
        session_id: UUID,
    ) -> ProtocolSession:

        with self._lock:
            return self._get(session_id)

    def list(
        self,
    ) -> tuple[ProtocolSession, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._sessions.values(),
                    key=lambda session: (
                        session.created_at,
                        str(session.session_id),
                    ),
                )
            )

    def _get(
        self,
        session_id: UUID,
    ) -> ProtocolSession:

        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise LookupError(
                f"Session not found: {session_id}"
            ) from exc


__all__ = [
    "SessionState",
    "ProtocolSession",
    "SessionManager",
]
