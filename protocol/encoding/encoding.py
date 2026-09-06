from __future__ import annotations

import json
from typing import Any, Mapping


class ProtocolEncodingError(ValueError):
    """Raised when protocol data cannot be encoded or decoded."""


class JSONCodec:
    """Canonical deterministic JSON codec for protocol messages."""

    @staticmethod
    def encode(value: Mapping[str, Any]) -> bytes:
        try:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ProtocolEncodingError(
                "Unable to encode protocol payload"
            ) from exc

    @staticmethod
    def decode(data: bytes) -> dict[str, Any]:
        if not isinstance(data, bytes):
            raise ProtocolEncodingError("Encoded data must be bytes")

        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolEncodingError(
                "Unable to decode protocol payload"
            ) from exc

        if not isinstance(value, dict):
            raise ProtocolEncodingError(
                "Protocol payload root must be an object"
            )

        return value


__all__ = ["JSONCodec", "ProtocolEncodingError"]
