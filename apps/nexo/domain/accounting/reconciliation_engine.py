
# reconciliation_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations

from typing import Dict, List
import uuid

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(1, "reconciliations", (
        "CREATE TABLE IF NOT EXISTS reconciliations ("
        " recon_id TEXT PRIMARY KEY,"
        " matched INTEGER NOT NULL,"
        " missing_in_bank INTEGER NOT NULL,"
        " missing_in_internal INTEGER NOT NULL,"
        " status TEXT NOT NULL,"
        " generated_at REAL NOT NULL)",
    )),
)


class ReconciliationEngine:
    """Motor de conciliacion: interno vs
    bancario, por clave (id + monto)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.recon",
                        _MIGRATIONS).run(clock)

    def reconcile(self, internal_records: List[dict],
                  bank_records: List[dict]) -> Dict:
        def clave(item):
            if isinstance(item, dict):
                return (str(item.get("id",
                        item.get("reference_id",
                        item.get("entry_id", "")))),
                        str(item.get("amount", "")))
            return str(item)

        bank_map = {}
        for b in bank_records:
            bank_map.setdefault(
                clave(b), []).append(b)

        matched = []
        missing_bank = []
        used = set()
        for item in internal_records:
            k = clave(item)
            if k in bank_map and bank_map[k]:
                matched.append(item)
                used.add(id(bank_map[k].pop(0)))
            else:
                missing_bank.append(item)

        missing_internal = [
            b for b in bank_records
            if id(b) not in used]

        recon_id = f"REC-{uuid.uuid4()}"
        status = ("RECONCILED"
                  if not missing_bank
                  and not missing_internal
                  else "DIFFERENCES_FOUND")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO reconciliations"
                " (recon_id, matched, missing_in_bank,"
                " missing_in_internal, status, generated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (recon_id, len(matched),
                 len(missing_bank),
                 len(missing_internal),
                 status, now))
        return {"recon_id": recon_id,
                "matched": len(matched),
                "missing_in_bank": len(missing_bank),
                "missing_in_internal":
                len(missing_internal),
                "internal_records":
                len(internal_records),
                "bank_records": len(bank_records),
                "status": status,
                "generated_at": now}
