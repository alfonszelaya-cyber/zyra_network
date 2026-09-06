from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from protocol.messages.messages import ProtocolMessage


@dataclass(frozen=True, slots=True)
class SDKConfiguration:
    protocol_version: str = "1"
    sender_id: str = "anonymous"
    default_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.protocol_version.strip():
            raise ValueError(
                "protocol_version cannot be empty"
            )

        if not self.sender_id.strip():
            raise ValueError(
                "sender_id cannot be empty"
            )

        if self.default_timeout_seconds <= 0:
            raise ValueError(
                "default_timeout_seconds must be positive"
            )


class ProtocolSDK:
    """
    Stable application-facing facade
    for the protocol layer.
    """

    def __init__(
        self,
        configuration: SDKConfiguration | None = None,
    ) -> None:

        self.configuration = (
            configuration
            or SDKConfiguration()
        )

    def message(
        self,
        message_type: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: UUID | None = None,
        reply_to: UUID | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ProtocolMessage:

        return ProtocolMessage.create(
            message_type=message_type,
            sender_id=(
                self.configuration.sender_id
            ),
            payload=payload,
            correlation_id=correlation_id,
            reply_to=reply_to,
            headers=headers,
        )

    def identity(self) -> str:
        return self.configuration.sender_id

    def version(self) -> str:
        return self.configuration.protocol_version


__all__ = [
    "SDKConfiguration",
    "ProtocolSDK",
]
