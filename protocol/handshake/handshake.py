from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandshakeRequest:
    protocol_version: str
    node_id: str
    nonce: str

    @classmethod
    def create(
        cls,
        protocol_version: str,
        node_id: str,
    ) -> "HandshakeRequest":
        if not protocol_version.strip():
            raise ValueError("Protocol version cannot be empty")
        if not node_id.strip():
            raise ValueError("Node ID cannot be empty")

        return cls(
            protocol_version=protocol_version.strip(),
            node_id=node_id.strip(),
            nonce=secrets.token_urlsafe(24),
        )


@dataclass(frozen=True, slots=True)
class HandshakeResponse:
    accepted: bool
    protocol_version: str
    node_id: str
    reason: str | None = None


class HandshakeProcessor:
    def __init__(self, supported_versions: set[str]) -> None:
        versions = frozenset(
            version.strip()
            for version in supported_versions
            if version.strip()
        )

        if not versions:
            raise ValueError(
                "At least one protocol version is required"
            )

        self._supported_versions = versions

    def process(
        self,
        request: HandshakeRequest,
        local_node_id: str,
    ) -> HandshakeResponse:
        if request.protocol_version not in self._supported_versions:
            return HandshakeResponse(
                accepted=False,
                protocol_version=request.protocol_version,
                node_id=local_node_id,
                reason="Unsupported protocol version",
            )

        if not local_node_id.strip():
            raise ValueError("Local node ID cannot be empty")

        return HandshakeResponse(
            accepted=True,
            protocol_version=request.protocol_version,
            node_id=local_node_id.strip(),
        )


__all__ = [
    "HandshakeRequest",
    "HandshakeResponse",
    "HandshakeProcessor",
]
