"""Consumer-side deduplication (inbox pattern).

``process`` records the event and runs the handler inside ONE
transaction: the dedup record and the business effect commit
atomically, so at-least-once delivery never becomes a
duplicated effect.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

from shared_engines.common.clocks import Clock
from shared_engines.events.contracts import Event
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import Migration, MigrationRunner

MIGRATIONS = (
    Migration(
        1,
        "events_inbox",
        (
            "CREATE TABLE events_inbox ("
            " event_id TEXT PRIMARY KEY,"
            " event_type TEXT NOT NULL,"
            " processed_at REAL NOT NULL)",
        ),
    ),
)


class Inbox:
    """Deduplicates deliveries: record and effect commit together."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "events.inbox", MIGRATIONS).run(clock)

    def process(
        self, event: Event, handler: Callable[[Event], None]
    ) -> bool:
        """Applies handler once per event_id; False for duplicates."""
        try:
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO events_inbox"
                    " (event_id, event_type, processed_at)"
                    " VALUES (?, ?, ?)",
                    (
                        event.event_id,
                        event.event_type,
                        self._clock.now(),
                    ),
                )
                handler(event)
        except sqlite3.IntegrityError:
            return False
        return True
