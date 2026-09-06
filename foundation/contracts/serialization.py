from __future__ import annotations

import json
from typing import Any, Mapping


class ContractSerializationError(ValueError):
    """Raised when contract serialization fails."""


def to_json(
    value: Mapping[str, Any],
    *,
    sort_keys: bool = True,
) -> str:
    if not isinstance(value, Mapping):
        raise ContractSerializationError(
            "Contract value must be a mapping"
        )

    try:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=sort_keys,
        )
    except (TypeError, ValueError) as exc:
        raise ContractSerializationError(
            "Contract contains non-serializable data"
        ) from exc


def from_json(value: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise ContractSerializationError(
            "JSON input must be a string"
        )

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ContractSerializationError(
            "Invalid contract JSON"
        ) from exc

    if not isinstance(decoded, dict):
        raise ContractSerializationError(
            "Contract JSON root must be an object"
        )

    return decoded
