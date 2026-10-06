
"""Family Governance - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "family_governance_decisions", (
        "CREATE TABLE IF NOT EXISTS family_governance_decisions (decision_id TEXT PRIMARY KEY, subject TEXT NOT NULL, participants_json TEXT NOT NULL DEFAULT '[]', resolution TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'APPROVED', created_at REAL NOT NULL)",
    )),
)

class FamilyGovernanceEngine:
    """Gobierno familiar (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.familygov",
                        _MIGRATIONS).run(clock)

    def register_decision(self, *, subject,
                          participants, resolution):
        import json as _j
        did = "FGV-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO family_governance_decisions"
                " (decision_id, subject,"
                " participants_json, resolution, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, 'APPROVED', ?)",
                (did, subject,
                 _j.dumps(participants, default=str),
                 resolution, now))
        return {"decision_id": did,
                "subject": subject,
                "participants": participants,
                "resolution": resolution,
                "status": "APPROVED"}

    def get_decisions(self):
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM family_governance_decisions"
            " ORDER BY created_at")
        return [{"decision_id": str(r["decision_id"]),
                 "subject": str(r["subject"]),
                 "participants": _j.loads(
                     str(r["participants_json"])),
                 "resolution": str(r["resolution"]),
                 "status": str(r["status"])}
                for r in rows]
