"""Lifelong history: the Network's civic timeline.

The go.sv-style goal: a person's first registration
(e.g. a newborn in a health app) creates the trust
ZID, and from that moment every authorized app adds
permanent records to ONE lifelong timeline:

    birth_registration -> health -> education ->
    civil -> employment -> ...

Guarantees:

- Append-only: entries are never edited or deleted.
- Tamper-evident: each entry hashes its content
  together with the previous entry's hash (per-ZID
  chain); any historic modification breaks the
  chain and verify_chain() detects it.
- Only apps registered via ProfileRegistry may
  append (app existence checked in app_registry).
- Every append is audited and emits
  network.history.appended to the Outbox.
- Transactions never nest: the entry + outbox
  event share one short transaction; the audit
  append runs afterwards on its own.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_HISTORY_APPENDED = (
    "network.history.appended"
)

ENTRY_TYPES = (
    "birth_registration",
    "health",
    "education",
    "civil_status",
    "employment",
    "asset",
    "other",
)

_MIGRATIONS = (
    Migration(
        1,
        "network_life_history",
        (
            "CREATE TABLE life_history_entries ("
            " zid TEXT NOT NULL,"
            " entry_seq INTEGER NOT NULL,"
            " entry_type TEXT NOT NULL,"
            " actor_app TEXT NOT NULL,"
            " payload TEXT NOT NULL,"
            " content_hash TEXT NOT NULL,"
            " prev_hash TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " PRIMARY KEY (zid, entry_seq))",
            "CREATE INDEX life_history_zid"
            " ON life_history_entries"
            " (zid, entry_seq)",
        ),
    ),
)


@dataclass(frozen=True)
class HistoryEntry:
    zid: str
    entry_seq: int
    entry_type: str
    actor_app: str
    payload: dict[str, object]
    content_hash: str
    prev_hash: str
    created_at: float


def _content_hash(
    *,
    prev_hash: str,
    entry_seq: int,
    entry_type: str,
    actor_app: str,
    payload_json: str,
    created_at: float,
) -> str:
    src = canonical_json_dumps(
        {
            "seq": entry_seq,
            "type": entry_type,
            "actor": actor_app,
            "payload": payload_json,
            "at": created_at,
            "prev": prev_hash,
        }
    )
    return hashlib.sha256(
        src.encode("utf-8")
    ).hexdigest()


class LifeHistory:
    """Append-only lifelong timeline per ZID."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        MigrationRunner(
            db,
            "network.life_history",
            _MIGRATIONS,
        ).run(clock)

    def append(
        self,
        *,
        zid: str,
        entry_type: str,
        actor_app: str,
        payload: dict[str, object],
    ) -> HistoryEntry:
        """Add one permanent record. The app must
        be registered and the entry type known."""
        require_non_empty_str(zid, "zid")
        require_non_empty_str(
            entry_type, "entry_type"
        )
        require_non_empty_str(
            actor_app, "actor_app"
        )
        if entry_type not in ENTRY_TYPES:
            raise ValueError(
                f"unknown entry type:"
                f" {entry_type}"
            )
        if not payload:
            raise ValueError(
                "payload required"
            )
        row = self._db.query_one(
            "SELECT 1 FROM app_registry"
            " WHERE app_id = ?",
            (actor_app,),
        )
        if row is None:
            raise PermissionError(
                "app not registered:"
                f" {actor_app}"
            )
        payload_json = canonical_json_dumps(
            payload
        )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            last = cursor.execute(
                "SELECT entry_seq, content_hash"
                " FROM life_history_entries"
                " WHERE zid = ?"
                " ORDER BY entry_seq DESC"
                " LIMIT 1",
                (zid,),
            ).fetchone()
            if last is None:
                seq = 1
                prev_hash = "GENESIS"
            else:
                seq = (
                    int(last["entry_seq"])
                    + 1
                )
                prev_hash = str(
                    last["content_hash"]
                )
            content = _content_hash(
                prev_hash=prev_hash,
                entry_seq=seq,
                entry_type=entry_type,
                actor_app=actor_app,
                payload_json=payload_json,
                created_at=now,
            )
            cursor.execute(
                "INSERT INTO"
                " life_history_entries"
                " (zid, entry_seq,"
                "  entry_type, actor_app,"
                "  payload, content_hash,"
                "  prev_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, ?)",
                (
                    zid,
                    seq,
                    entry_type,
                    actor_app,
                    payload_json,
                    content,
                    prev_hash,
                    now,
                ),
            )
            self._emit(
                cursor,
                zid=zid,
                seq=seq,
                entry_type=entry_type,
                actor_app=actor_app,
            )
        self._audit.append(
            event_type=(
                EVENT_HISTORY_APPENDED
            ),
            actor=actor_app,
            subject=zid,
            payload={
                "seq": seq,
                "entry_type": entry_type,
            },
        )
        return HistoryEntry(
            zid=zid,
            entry_seq=seq,
            entry_type=entry_type,
            actor_app=actor_app,
            payload=payload,
            content_hash=content,
            prev_hash=prev_hash,
            created_at=now,
        )

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        zid: str,
        seq: int,
        entry_type: str,
        actor_app: str,
    ) -> None:
        event_id = hashlib.sha256(
            canonical_json_dumps(
                {
                    "z": zid,
                    "s": seq,
                    "t": entry_type,
                    "ts": self._clock.now(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": (
                        EVENT_HISTORY_APPENDED
                    ),
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                event_id,
                EVENT_HISTORY_APPENDED,
                zid,
                self._clock.now(),
                canonical_json_dumps(
                    {
                        "seq": seq,
                        "entry_type": (
                            entry_type
                        ),
                        "actor": actor_app,
                    }
                ),
                fp,
            ),
        )

    def timeline(
        self,
        *,
        zid: str,
        limit: int = 1000,
    ) -> tuple[HistoryEntry, ...]:
        require_non_empty_str(zid, "zid")
        rows = self._db.query_all(
            "SELECT * FROM"
            " life_history_entries"
            " WHERE zid = ?"
            " ORDER BY entry_seq ASC"
            " LIMIT ?",
            (zid, limit),
        )
        return tuple(
            HistoryEntry(
                zid=zid,
                entry_seq=int(
                    r["entry_seq"]
                ),
                entry_type=str(
                    r["entry_type"]
                ),
                actor_app=str(
                    r["actor_app"]
                ),
                payload=self._loads(
                    str(r["payload"])
                ),
                content_hash=str(
                    r["content_hash"]
                ),
                prev_hash=str(
                    r["prev_hash"]
                ),
                created_at=float(
                    r["created_at"]
                ),
            )
            for r in rows
        )

    @staticmethod
    def _loads(raw: str) -> dict[str, object]:
        data = json.loads(raw)
        assert isinstance(data, dict)
        return data

    def verify_chain(
        self, *, zid: str
    ) -> bool:
        """Recompute the per-ZID hash chain;
        False if any historic entry was altered."""
        entries = self.timeline(zid=zid)
        prev = "GENESIS"
        for entry in entries:
            expected = _content_hash(
                prev_hash=prev,
                entry_seq=entry.entry_seq,
                entry_type=entry.entry_type,
                actor_app=entry.actor_app,
                payload_json=(
                    canonical_json_dumps(
                        entry.payload
                    )
                ),
                created_at=entry.created_at,
            )
            if (
                entry.content_hash
                != expected
                or entry.prev_hash != prev
            ):
                return False
            prev = entry.content_hash
        return True
