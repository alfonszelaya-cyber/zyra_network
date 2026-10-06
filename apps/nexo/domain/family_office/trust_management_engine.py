
"""Trust Management - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "family_trusts", (
        "CREATE TABLE IF NOT EXISTS family_trusts (trust_id TEXT PRIMARY KEY, trust_name TEXT NOT NULL, jurisdiction TEXT NOT NULL, beneficiaries_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class TrustManagementEngine:
    """Gestion de Trusts (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.trusts",
                        _MIGRATIONS).run(clock)

    def create_trust(self, *, trust_name, jurisdiction,
                     beneficiaries):
        import json as _j
        tid = "TRUST-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO family_trusts"
                " (trust_id, trust_name, jurisdiction,"
                " beneficiaries_json, status, created_at)"
                " VALUES (?, ?, ?, ?, 'ACTIVE', ?)",
                (tid, trust_name, jurisdiction,
                 _j.dumps(beneficiaries, default=str),
                 now))
        return {"trust_id": tid,
                "trust_name": trust_name,
                "jurisdiction": jurisdiction,
                "beneficiaries": beneficiaries,
                "status": "ACTIVE"}

    def get_trusts(self):
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM family_trusts ORDER BY created_at")
        return [{"trust_id": str(r["trust_id"]),
                 "trust_name": str(r["trust_name"]),
                 "jurisdiction": str(r["jurisdiction"]),
                 "beneficiaries": _j.loads(
                     str(r["beneficiaries_json"])),
                 "status": str(r["status"])}
                for r in rows]
