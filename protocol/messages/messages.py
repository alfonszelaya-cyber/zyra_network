from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

# IMPORT DIRECTO:
# evita depender del contenido exportado por protocol.encoding.__init__
from protocol.encoding.encoding import ProtocolEncoder


PROTOCOL_MESSAGE_VERSION = "1"


@dataclass(frozen=True, slots=True)
class ProtocolMessage:
    message_id: UUID
    message_type: str
    version: str
    sender_id: str
    payload: Mapping[str, Any]
    created_at: datetime
    correlation_id: UUID | None = None
    reply_to: UUID | None = None
    headers: Mapping[str, str] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        message_type: str,
        sender_id: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: UUID | None = None,
        reply_to: UUID | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> "ProtocolMessage":

        message_type = message_type.strip()
        sender_id = sender_id.strip()

        if not message_type:
            raise ValueError(
                "message_type cannot be empty"
            )

        if not sender_id:
            raise ValueError(
                "sender_id cannot be empty"
            )

        if not isinstance(payload, Mapping):
            raise TypeError(
                "payload must be a mapping"
            )

        return cls(
            message_id=uuid4(),
            message_type=message_type,
            version=PROTOCOL_MESSAGE_VERSION,
            sender_id=sender_id,
            payload=dict(payload),
            created_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            reply_to=reply_to,
            headers=dict(headers or {}),
        )

    def __post_init__(self) -> None:
        if not isinstance(
            self.message_id,
            UUID,
        ):
            raise TypeError(
                "message_id must be UUID"
            )

        if not self.message_type.strip():
            raise ValueError(
                "message_type cannot be empty"
            )

        if not self.version.strip():
            raise ValueError(
                "version cannot be empty"
            )

        if not self.sender_id.strip():
            raise ValueError(
                "sender_id cannot be empty"
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(
            self,
            "payload",
            dict(self.payload),
        )

        object.__setattr__(
            self,
            "headers",
            dict(self.headers),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "message_id": str(self.message_id),
            "message_type": self.message_type,
            "version": self.version,
            "sender_id": self.sender_id,
            "payload": dict(self.payload),
            "created_at": self.created_at.astimezone(
                timezone.utc
            ).isoformat(),
            "correlation_id": (
                str(self.correlation_id)
                if self.correlation_id is not None
                else None
            ),
            "reply_to": (
                str(self.reply_to)
                if self.reply_to is not None
                else None
            ),
            "headers": dict(
                sorted(
                    self.headers.items()
                )
            ),
        }

    def canonical_bytes(self) -> bytes:
        return ProtocolEncoder.encode(
            self.canonical_dict()
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(
            self.canonical_bytes()
        ).hexdigest()


class MessageFactory:

    def create(
        self,
        message_type: str,
        sender_id: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: UUID | None = None,
        reply_to: UUID | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ProtocolMessage:

        return ProtocolMessage.create(
            message_type=message_type,
            sender_id=sender_id,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=reply_to,
            headers=headers,
        )


__all__ = [
    "PROTOCOL_MESSAGE_VERSION",
    "ProtocolMessage",
    "MessageFactory",
]
