from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class ProtocolEncoder:
    """
    Canonical JSON encoder for ZYRA protocol messages.

    The encoding is deterministic:
    - UTF-8
    - sorted object keys
    - compact separators
    - no ASCII escaping
    """

    @staticmethod
    def encode(value: Mapping[str, Any]) -> bytes:
        if not isinstance(value, Mapping):
            raise TypeError(
                "Protocol payload must be a mapping"
            )

        try:
            encoded = json.dumps(
                dict(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Protocol payload is not JSON serializable"
            ) from exc

        return encoded.encode("utf-8")

    @staticmethod
    def decode(payload: bytes) -> dict[str, Any]:
        if not isinstance(payload, bytes):
            raise TypeError(
                "Protocol payload must be bytes"
            )

        if not payload:
            raise ValueError(
                "Protocol payload cannot be empty"
            )

        try:
            decoded = payload.decode("utf-8")
            value = json.loads(decoded)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Invalid protocol payload"
            ) from exc

        if not isinstance(value, dict):
            raise ValueError(
                "Protocol payload must decode to an object"
            )

        return value


__all__ = ["ProtocolEncoder"]
