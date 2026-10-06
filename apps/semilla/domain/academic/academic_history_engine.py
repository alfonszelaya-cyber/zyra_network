
"""Academic History Engine - historial hash-chain
verificable (SM1)."""
from __future__ import annotations
import hashlib
from typing import List
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_history", (
        "CREATE TABLE IF NOT EXISTS sm_history (seq INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL, created_at REAL NOT NULL)",
    )),
)

class AcademicHistoryEngine:
    """Historial academico encadenado."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.history",
                        _MIGRATIONS).run(clock)

    def _hash(self, prev, payload) -> str:
        return hashlib.sha256(
            (str(prev) + "|" + str(payload))
            .encode("utf-8")).hexdigest()

    def append(self, *, student_id, event_type,
               detail="") -> dict:
        row = self._db.query_one(
            "SELECT entry_hash FROM sm_history"
            " ORDER BY seq DESC LIMIT 1")
        prev = (str(row["entry_hash"])
                if row else "GENESIS")
        payload = (student_id + "|"
                   + event_type + "|"
                   + str(detail))
        h = self._hash(prev, payload)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_history"
                " (student_id, event_type,"
                " detail, prev_hash, entry_hash,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (student_id, event_type,
                 str(detail), prev, h, now))
            seq = cursor.execute(
                "SELECT seq FROM sm_history"
                " ORDER BY seq DESC LIMIT 1"
                ).fetchone()
        return {"seq": int(seq["seq"]),
                "entry_hash": h}

    def verify(self, student_id="") -> bool:
        if student_id:
            rows = self._db.query_all(
                "SELECT * FROM sm_history WHERE"
                " student_id = ? ORDER BY seq",
                (student_id,))
        else:
            rows = self._db.query_all(
                "SELECT * FROM sm_history"
                " ORDER BY seq")
        prev = "GENESIS"
        for r in rows:
            payload = (str(r["student_id"])
                       + "|"
                       + str(r["event_type"])
                       + "|"
                       + str(r["detail"]))
            expect = self._hash(prev, payload)
            if (str(r["prev_hash"]) != prev
                    or str(r["entry_hash"])
                    != expect):
                return False
            prev = str(r["entry_hash"])
        return True

    def history_of(self, student_id
                   ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_history WHERE"
            " student_id = ? ORDER BY seq",
            (student_id,))
        return [{"seq": int(r["seq"]),
                 "event_type":
                     str(r["event_type"]),
                 "detail": str(r["detail"]),
                 "entry_hash":
                     str(r["entry_hash"])}
                for r in rows]
