"""Stable ids and hashing."""
from __future__ import annotations

import hashlib
import uuid

from shared_engines.common.serialization import canonical_json_dumps


def new_id() -> str:
    return uuid.uuid4().hex


def stable_hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def payload_fingerprint(payload: object) -> str:
    return stable_hash(canonical_json_dumps(payload))
