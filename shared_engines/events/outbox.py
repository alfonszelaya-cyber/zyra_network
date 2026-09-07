"""Transactional outbox with at-least-once dispatch.

``enqueue_in_transaction`` runs inside the SAME transaction as
the state change; delivery happens afterwards. A crash between
handler and mark causes redelivery; consumers suppress
duplicates via the Inbox.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

from shared_engines.common.clocks import Clock
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.events.contracts import Event
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import Migration, MigrationRunner

MIGRATIONS = (
    Migration(
        1,
        "events_outbox",
        (
            "CREATE TABLE events_outbox ("
            " event_id TEXT PRIMARY KEY,"
            " event_type TEXT NOT NULL,"
            " aggregate_id TEXT NOT NULL,"
            " schema_version INTEGER NOT NULL,"
            " envelope_version INTEGER NOT NULL,"
            " created_at REAL NOT NULL,"
            " payload TEXT NOT NULL,"
            " fingerprint TEXT NOT NULL,"
            " published_at REAL)",
            "CREATE INDEX events_outbox_pending"
            " ON events_outbox (published_at, created_at)",
        ),
    ),
)


class Outbox:
    """Persists events atomically with the state producing them."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def ensure_schema(self) -> None:
        MigrationRunner(self._db, "events.outbox", MIGRATIONS).run(
            self._clock
        )

    def enqueue_in_transaction(
        self, cursor: sqlite3.Cursor, event: Event
    ) -> None:
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type, aggregate_id, schema_version,"
            "  envelope_version, created_at, payload, fingerprint,"
            "  published_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                event.event_id,
                event.event_type,
                event.aggregate_id,
                event.schema_version,
                event.envelope_version,
                event.timestamp,
                canonical_json_dumps(dict(event.payload)),
                event.fingerprint,
            ),
        )

    def enqueue(self, event: Event) -> None:
        with self._db.transaction() as cursor:
            self.enqueue_in_transaction(cursor, event)

    def pending(self, limit: int = 100) -> tuple[Event, ...]:
        rows = self._db.query_all(
            "SELECT * FROM events_outbox WHERE published_at IS NULL"
            " ORDER BY created_at, event_id LIMIT ?",
            (limit,),
        )
        return tuple(self._to_event(row) for row in rows)

    def dispatch_pending(
        self,
        handler: Callable[[Event], None],
        *,
        batch_size: int = 100,
    ) -> int:
        delivered = 0
        for event in self.pending(batch_size):
            handler(event)
            self._db.execute(
                "UPDATE events_outbox SET published_at = ?"
                " WHERE event_id = ? AND published_at IS NULL",
                (self._clock.now(), event.event_id),
            )
            delivered += 1
        return delivered

    @staticmethod
    def _to_event(row: sqlite3.Row) -> Event:
        return Event(
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            aggregate_id=str(row["aggregate_id"]),
            schema_version=int(row["schema_version"]),
            envelope_version=int(row["envelope_version"]),
            timestamp=float(row["created_at"]),
            payload=canonical_json_loads(str(row["payload"])),
            fingerprint=str(row["fingerprint"]),
        )
