"""Cryptographic API keys: one per client, hash-stored, audited.

Key format: ``zy_<keyid>_<secret>``
- keyid: 16 hex chars (public identifier)
- secret: 48 hex chars (192-bit CSPRNG secret, shown ONCE)

The database stores ONLY sha256(full_key). A stolen database
does not leak usable keys. Verification compares hashes in
constant time. Rotation creates a new key and revokes the
old one. Every lifecycle event is audited.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Final

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.validation import require_non_empty_str
from shared_engines.hardening.errors import (
    ApiKeyNotFoundError,
    ApiKeyRevokedError,
    InvalidApiKeyError,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

KEY_PREFIX: Final[str] = "zy"
KEY_ID_LEN: Final[int] = 16
SECRET_LEN: Final[int] = 48

API_KEYS_MIGRATIONS = (
    Migration(
        1,
        "api_keys",
        (
            "CREATE TABLE api_keys ("
            " key_id TEXT PRIMARY KEY,"
            " label TEXT NOT NULL,"
            " key_hash TEXT NOT NULL,"
            " active INTEGER NOT NULL DEFAULT 1,"
            " created_by TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " revoked_at REAL)",
            "CREATE INDEX api_keys_active"
            " ON api_keys (active)",
        ),
    ),
)


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    label: str
    active: bool
    created_by: str
    created_at: float
    revoked_at: float | None


class ApiKeyManager:
    """Creates, verifies, rotates and revokes client keys."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        MigrationRunner(
            db, "hardening.keys", API_KEYS_MIGRATIONS
        ).run(clock)

    @staticmethod
    def _hash_key(full_key: str) -> str:
        return hashlib.sha256(
            full_key.encode("utf-8")
        ).hexdigest()

    def generate(
        self, *, label: str, created_by: str
    ) -> tuple[str, ApiKeyRecord]:
        """Creates a new key. Returns (full_key, record).

        The full key is shown EXACTLY ONCE; the caller must
        store it securely. Only its hash is persisted.
        """
        require_non_empty_str(label, "label")
        require_non_empty_str(created_by, "created_by")
        key_id = secrets.token_hex(KEY_ID_LEN // 2)
        secret = secrets.token_hex(SECRET_LEN // 2)
        full_key = f"{KEY_PREFIX}_{key_id}_{secret}"
        key_hash = self._hash_key(full_key)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO api_keys"
                " (key_id, label, key_hash, active,"
                "  created_by, created_at, revoked_at)"
                " VALUES (?, ?, ?, 1, ?, ?, NULL)",
                (key_id, label, key_hash, created_by, now),
            )
        self._audit.append(
            event_type="hardening.api_key.created",
            actor=created_by,
            subject=key_id,
            payload={"label": label},
        )
        row = self._db.query_one(
            "SELECT * FROM api_keys WHERE key_id = ?",
            (key_id,),
        )
        if row is None:
            raise IntegrityError("key row vanished after insert")
        return full_key, self._record_from_row(row)

    def verify(self, full_key: str) -> ApiKeyRecord:
        """Verifies a presented key; raises on any failure.

        Hash comparison is constant-time: response timing
        leaks nothing about key validity.
        """
        require_non_empty_str(full_key, "full_key")
        parts = full_key.split("_")
        if (
            len(parts) != 3
            or parts[0] != KEY_PREFIX
            or len(parts[1]) != KEY_ID_LEN
            or len(parts[2]) != SECRET_LEN
        ):
            raise InvalidApiKeyError("malformed key format")
        key_id = parts[1]
        row = self._db.query_one(
            "SELECT * FROM api_keys WHERE key_id = ?",
            (key_id,),
        )
        if row is None:
            raise InvalidApiKeyError("unknown key")
        stored_hash = str(row["key_hash"])
        computed = self._hash_key(full_key)
        if not hmac.compare_digest(stored_hash, computed):
            raise InvalidApiKeyError("key does not match")
        if not bool(int(row["active"])):
            raise ApiKeyRevokedError(
                f"key {key_id} was revoked"
            )
        return self._record_from_row(row)

    def revoke(self, key_id: str, *, revoked_by: str) -> None:
        require_non_empty_str(key_id, "key_id")
        require_non_empty_str(revoked_by, "revoked_by")
        row = self._db.query_one(
            "SELECT active FROM api_keys WHERE key_id = ?",
            (key_id,),
        )
        if row is None:
            raise ApiKeyNotFoundError(
                f"unknown key: {key_id}"
            )
        if not bool(int(row["active"])):
            raise ApiKeyRevokedError(
                f"key {key_id} already revoked"
            )
        now = self._clock.now()
        self._db.execute(
            "UPDATE api_keys SET active = 0, revoked_at = ?"
            " WHERE key_id = ?",
            (now, key_id),
        )
        self._audit.append(
            event_type="hardening.api_key.revoked",
            actor=revoked_by,
            subject=key_id,
            payload={},
        )

    def rotate(
        self, key_id: str, *, rotated_by: str
    ) -> tuple[str, ApiKeyRecord]:
        """Revokes old key and creates a fresh one."""
        require_non_empty_str(rotated_by, "rotated_by")
        row = self._db.query_one(
            "SELECT label FROM api_keys WHERE key_id = ?",
            (key_id,),
        )
        if row is None:
            raise ApiKeyNotFoundError(
                f"unknown key: {key_id}"
            )
        self.revoke(key_id, revoked_by=rotated_by)
        return self.generate(
            label=str(row["label"]) + "-rotated",
            created_by=rotated_by,
        )

    def list_active(self) -> tuple[ApiKeyRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM api_keys WHERE active = 1"
            " ORDER BY created_at, key_id"
        )
        return tuple(self._record_from_row(r) for r in rows)

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ApiKeyRecord:
        revoked_at = row["revoked_at"]
        return ApiKeyRecord(
            key_id=str(row["key_id"]),
            label=str(row["label"]),
            active=bool(int(row["active"])),
            created_by=str(row["created_by"]),
            created_at=float(row["created_at"]),
            revoked_at=(
                None if revoked_at is None else float(revoked_at)
            ),
        )
