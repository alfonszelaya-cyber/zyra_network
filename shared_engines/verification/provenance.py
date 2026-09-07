"""Content provenance: tamper-evident chain of custody.

Every action on a media item (registered, transferred,
annotated, verified, attested) is appended to a
hash-chained log specific to that media. Anyone can verify
the chain integrity by recomputing hashes from the events,
without access to the storage.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import stable_hash
from shared_engines.common.validation import require_non_empty_str
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

GENESIS_HASH = "0" * 64

PROVENANCE_MIGRATIONS = (
    Migration(
        1,
        "provenance",
        (
            "CREATE TABLE media_provenance ("
            " sequence INTEGER NOT NULL,"
            " media_id TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " action TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " occurred_at REAL NOT NULL,"
            " previous_hash TEXT NOT NULL,"
            " event_hash TEXT NOT NULL,"
            " PRIMARY KEY (media_id, sequence))",
            "CREATE INDEX provenance_media"
            " ON media_provenance (media_id, sequence)",
        ),
    ),
)


@dataclass(frozen=True)
class ProvenanceEvent:
    sequence: int
    media_id: str
    actor_zid: str
    action: str
    detail: str
    occurred_at: float
    previous_hash: str
    event_hash: str


class ProvenanceChain:
    """Per-media hash-chained custody log."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "verification.provenance", PROVENANCE_MIGRATIONS
        ).run(clock)

    def record(
        self,
        *,
        media_id: str,
        actor_zid: str,
        action: str,
        detail: str,
    ) -> ProvenanceEvent:
        require_non_empty_str(media_id, "media_id")
        require_non_empty_str(actor_zid, "actor_zid")
        require_non_empty_str(action, "action")
        require_non_empty_str(detail, "detail")
        with self._db.transaction() as cursor:
            last = cursor.execute(
                "SELECT sequence, event_hash FROM media_provenance"
                " WHERE media_id = ?"
                " ORDER BY sequence DESC LIMIT 1",
                (media_id,),
            ).fetchone()
            sequence = (
                int(last["sequence"]) + 1
                if last is not None
                else 1
            )
            previous = (
                str(last["event_hash"])
                if last is not None
                else GENESIS_HASH
            )
            occurred_at = self._clock.now()
            event_hash = stable_hash(
                media_id,
                str(sequence),
                actor_zid,
                action,
                detail,
                f"{occurred_at:.6f}",
                previous,
            )
            cursor.execute(
                "INSERT INTO media_provenance"
                " (sequence, media_id, actor_zid, action, detail,"
                "  occurred_at, previous_hash, event_hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sequence,
                    media_id,
                    actor_zid,
                    action,
                    detail,
                    occurred_at,
                    previous,
                    event_hash,
                ),
            )
        return ProvenanceEvent(
            sequence=sequence,
            media_id=media_id,
            actor_zid=actor_zid,
            action=action,
            detail=detail,
            occurred_at=occurred_at,
            previous_hash=previous,
            event_hash=event_hash,
        )

    def history(
        self, media_id: str
    ) -> tuple[ProvenanceEvent, ...]:
        rows = self._db.query_all(
            "SELECT * FROM media_provenance WHERE media_id = ?"
            " ORDER BY sequence",
            (media_id,),
        )
        return tuple(
            ProvenanceEvent(
                sequence=int(row["sequence"]),
                media_id=str(row["media_id"]),
                actor_zid=str(row["actor_zid"]),
                action=str(row["action"]),
                detail=str(row["detail"]),
                occurred_at=float(row["occurred_at"]),
                previous_hash=str(row["previous_hash"]),
                event_hash=str(row["event_hash"]),
            )
            for row in rows
        )

    def verify_history(self, media_id: str) -> bool:
        """Recompute the chain; returns False if broken."""
        events = self.history(media_id)
        previous = GENESIS_HASH
        for index, event in enumerate(events, start=1):
            if event.sequence != index:
                return False
            if event.previous_hash != previous:
                return False
            expected = stable_hash(
                event.media_id,
                str(event.sequence),
                event.actor_zid,
                event.action,
                event.detail,
                f"{event.occurred_at:.6f}",
                previous,
            )
            if event.event_hash != expected:
                return False
            previous = event.event_hash
        return True
