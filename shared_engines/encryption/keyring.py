"""Durable keyring feeding EnvelopeCrypto.

Closes the security persistence gap: keys survive
restarts in SQLite. Rotation retires the current
version and persists the next one atomically;
retired versions are KEPT, so data sealed under
them stays openable forever (history, never
rewritten).
"""
from __future__ import annotations

import os
import sqlite3

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.encryption.contracts import (
    KeyRecord,
)
from shared_engines.encryption.errors import (
    KeyStateError,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

STATE_ACTIVE = "ACTIVE"
STATE_RETIRED = "RETIRED"
KEY_SIZE = 32

_MIGRATIONS = (
    Migration(
        1,
        "encryption_keys",
        (
            "CREATE TABLE encryption_keys ("
            " key_id TEXT PRIMARY KEY,"
            " version INTEGER NOT NULL"
            " UNIQUE,"
            " key_bytes BLOB NOT NULL,"
            " state TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " retired_at REAL)",
        ),
    ),
)


class DurableKeyring:
    """Persistent versioned KEK store."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        namespace: str = "default",
    ) -> None:
        self._db = db
        self._clock = clock
        self._ns = namespace
        MigrationRunner(
            db,
            f"encryption.{namespace}",
            _MIGRATIONS,
        ).run(clock)
        row = db.query_one(
            "SELECT 1 FROM"
            " encryption_keys LIMIT 1"
        )
        if row is None:
            self._create_version(1)

    def _create_version(
        self, version: int
    ) -> None:
        key_id = (
            f"kek-{self._ns}-v{version}"
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " encryption_keys"
                " (key_id, version,"
                "  key_bytes, state,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    key_id,
                    version,
                    os.urandom(KEY_SIZE),
                    STATE_ACTIVE,
                    self._clock.now(),
                ),
            )

    def load_keys(
        self,
    ) -> dict[int, bytes]:
        """All versions (active + retired)
        for EnvelopeCrypto: old envelopes
        stay openable."""
        rows = self._db.query_all(
            "SELECT version, key_bytes"
            " FROM encryption_keys"
            " ORDER BY version"
        )
        return {
            int(r["version"]): bytes(
                r["key_bytes"]
            )
            for r in rows
        }

    def current_version(self) -> int:
        row = self._db.query_one(
            "SELECT version FROM"
            " encryption_keys"
            " WHERE state = ?"
            " ORDER BY version DESC"
            " LIMIT 1",
            (STATE_ACTIVE,),
        )
        if row is None:
            raise NotFoundError(
                "no active key version"
            )
        return int(row["version"])

    def rotate(self) -> int:
        """Persist next version; retire the
        current one. Returns new version."""
        current = (
            self.current_version()
        )
        nxt = current + 1
        existing = self._db.query_one(
            "SELECT 1 FROM"
            " encryption_keys"
            " WHERE version = ?",
            (nxt,),
        )
        if existing is not None:
            raise KeyStateError(
                f"version {nxt}"
                " already exists"
            )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE encryption_keys"
                " SET state = ?,"
                " retired_at = ?"
                " WHERE version = ?",
                (
                    STATE_RETIRED,
                    self._clock.now(),
                    current,
                ),
            )
        self._create_version(nxt)
        return nxt

    def history(
        self,
    ) -> tuple[KeyRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM"
            " encryption_keys"
            " ORDER BY version"
        )
        return tuple(
            KeyRecord(
                key_id=str(
                    r["key_id"]
                ),
                version=int(
                    r["version"]
                ),
                state=str(
                    r["state"]
                ),
                created_at=float(
                    r["created_at"]
                ),
                retired_at=(
                    float(
                        r["retired_at"]
                    )
                    if r["retired_at"]
                    is not None
                    else None
                ),
            )
            for r in rows
        )


def _unused_row_guard(
    row: sqlite3.Row,
) -> int:
    return int(row["version"])
