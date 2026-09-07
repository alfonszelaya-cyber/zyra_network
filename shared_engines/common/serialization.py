"""Canonical JSON."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from shared_engines.common.errors import SerializationError

_SEP = (",", ":")


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return {"__decimal__": str(obj)}
    raise SerializationError(f"type {type(obj).__name__} not serializable")


def canonical_json_dumps(payload: Any) -> str:
    try:
        return json.dumps(
            payload, separators=_SEP, sort_keys=True,
            default=_default, ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise SerializationError(f"not serializable: {exc}") from exc


def canonical_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise SerializationError(f"invalid JSON: {exc}") from exc
