"""Append-only hash-chained audit trail with checkpoints.

Each record commits to the previous record's hash; any later
mutation breaks verification from that point. Checkpoints pin
(sequence, chain_hash) for external anchoring later. This
local chain is tamper-EVIDENT; it is not cryptographic proof
against an attacker with full database control.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError, ValidationError
from shared_engines.common.identifiers import (
    payload_fingerprint,
    stable_hash,
)
from shared_engines.common.validation import require_non_empty_str
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import Migration, MigrationRunner

GENESIS_HASH = "0" * 64

MIGRATIONS = (
    Migration(
        1,
        "audit_chain",
        (
            "CREATE TABLE audit_records ("
            " sequence INTEGER PRIMARY KEY,"
            " timestamp REAL NOT NULL,"
            " event_type TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " subject TEXT NOT NULL,"
            " payload_hash TEXT NOT NULL,"
            " previous_hash TEXT NOT NULL,"
            " record_hash TEXT NOT NULL)",
            "CREATE TABLE audit_checkpoints ("
            " sequence INTEGER PRIMARY KEY,"
            " chain_hash TEXT NOT NULL,"
            " checkpoint_hash TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    timestamp: float
    event_type: str
    actor: str
    subject: str
    payload_hash: str
    previous_hash: str
    record_hash: str


def _compute_record_hash(
    sequence: int,
    timestamp: float,
    event_type: str,
    actor: str,
    subject: str,
    payload_hash: str,
    previous_hash: str,
) -> str:
    return stable_hash(
        str(sequence),
        f"{timestamp:.6f}",
        event_type,
        actor,
        subject,
        payload_hash,
        previous_hash,
    )


class AuditTrail:
    """Tamper-evident chain; checkpoints pin the chain head."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "audit", MIGRATIONS).run(clock)

    def append(
        self,
        *,
        event_type: str,
        actor: str,
        subject: str,
        payload: Mapping[str, Any],
    ) -> AuditRecord:
        require_non_empty_str(event_type, "event_type")
        require_non_empty_str(actor, "actor")
        require_non_empty_str(subject, "subject")
        payload_hash = payload_fingerprint(dict(payload))
        with self._db.transaction() as cursor:
            last = cursor.execute(
                "SELECT sequence, record_hash FROM audit_records"
                " ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence = int(last["sequence"]) + 1 if last is not None else 1
            previous_hash = (
                str(last["record_hash"])
                if last is not None
                else GENESIS_HASH
            )
            timestamp = self._clock.now()
            record_hash = _compute_record_hash(
                sequence,
                timestamp,
                event_type,
                actor,
                subject,
                payload_hash,
                previous_hash,
            )
            cursor.execute(
                "INSERT INTO audit_records"
                " (sequence, timestamp, event_type, actor, subject,"
                "  payload_hash, previous_hash, record_hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sequence,
                    timestamp,
                    event_type,
                    actor,
                    subject,
                    payload_hash,
                    previous_hash,
                    record_hash,
                ),
            )
        return AuditRecord(
            sequence=sequence,
            timestamp=timestamp,
            event_type=event_type,
            actor=actor,
            subject=subject,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )

    def verify(self) -> int:
        """Recomputes the whole chain; raises on any break."""
        previous = GENESIS_HASH
        count = 0
        for row in self._db.query_all(
            "SELECT * FROM audit_records ORDER BY sequence"
        ):
            expected_sequence = count + 1
            if int(row["sequence"]) != expected_sequence:
                raise IntegrityError(
                    f"audit chain gap at sequence {expected_sequence}"
                )
            expected = _compute_record_hash(
                expected_sequence,
                float(row["timestamp"]),
                str(row["event_type"]),
                str(row["actor"]),
                str(row["subject"]),
                str(row["payload_hash"]),
                previous,
            )
            if str(row["previous_hash"]) != previous:
                raise IntegrityError(
                    f"chain broken at sequence {expected_sequence}:"
                    " previous hash mismatch"
                )
            if str(row["record_hash"]) != expected:
                raise IntegrityError(
                    f"record modified at sequence {expected_sequence}"
                )
            previous = str(row["record_hash"])
            count = expected_sequence
        return count

    def checkpoint(self) -> tuple[int, str]:
        count = self.verify()
        if count == 0:
            raise ValidationError(
                "cannot checkpoint an empty audit trail"
            )
        last = self._db.query_one(
            "SELECT sequence, record_hash FROM audit_records"
            " ORDER BY sequence DESC LIMIT 1"
        )
        if last is None:
            raise IntegrityError("audit trail vanished")
        sequence = int(last["sequence"])
        chain_hash = str(last["record_hash"])
        checkpoint_hash = stable_hash(
            "audit-checkpoint", str(sequence), chain_hash
        )
        self._db.execute(
            "INSERT INTO audit_checkpoints"
            " (sequence, chain_hash, checkpoint_hash, created_at)"
            " VALUES (?, ?, ?, ?)",
            (sequence, chain_hash, checkpoint_hash, self._clock.now()),
        )
        return sequence, checkpoint_hash

    def verify_checkpoints(self) -> int:
        """Re-verifies the chain and every checkpoint binding."""
        self.verify()
        rows = self._db.query_all(
            "SELECT * FROM audit_checkpoints ORDER BY sequence"
        )
        for row in rows:
            sequence = int(row["sequence"])
            record = self._db.query_one(
                "SELECT record_hash FROM audit_records"
                " WHERE sequence = ?",
                (sequence,),
            )
            if record is None or str(record["record_hash"]) != str(
                row["chain_hash"]
            ):
                raise IntegrityError(
                    f"checkpoint at {sequence} no longer matches chain"
                )
            expected = stable_hash(
                "audit-checkpoint", str(sequence), str(row["chain_hash"])
            )
            if expected != str(row["checkpoint_hash"]):
                raise IntegrityError(
                    f"checkpoint modified at sequence {sequence}"
                )
        return len(rows)
