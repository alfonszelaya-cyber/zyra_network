
# accounting_registry.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations

from typing import Dict, List, Optional
import uuid

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(1, "accounting_registry", (
        "CREATE TABLE IF NOT EXISTS accounting_registry ("
        " entry_id TEXT PRIMARY KEY,"
        " entry_json TEXT NOT NULL,"
        " account_code TEXT NOT NULL DEFAULT '',"
        " reference_id TEXT,"
        " created_at REAL NOT NULL)",
    )),
)


class AccountingRegistry:
    """Registro central de asientos (persistente)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.registry",
                        _MIGRATIONS).run(clock)

    def register(self, entry: dict) -> dict:
        import json as _j
        entry_id = entry.get(
            "entry_id", f"REG-{uuid.uuid4()}")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO accounting_registry"
                " (entry_id, entry_json, account_code,"
                " reference_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (entry_id,
                 _j.dumps(entry, default=str),
                 str(entry.get("account_code", "")),
                 entry.get("reference_id"), now))
        return entry

    def get_all(self) -> List[dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM accounting_registry"
            " ORDER BY created_at")
        return [_j.loads(str(r["entry_json"]))
                for r in rows]

    def get_by_id(self, entry_id: str) -> Optional[dict]:
        import json as _j
        row = self._db.query_one(
            "SELECT * FROM accounting_registry"
            " WHERE entry_id = ?", (entry_id,))
        return (_j.loads(str(row["entry_json"]))
                if row else None)

    def get_by_account(self, account_code: str) -> List[dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM accounting_registry"
            " WHERE account_code = ?", (account_code,))
        return [_j.loads(str(r["entry_json"]))
                for r in rows]

    def get_by_reference(self, reference_id: str) -> List[dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM accounting_registry"
            " WHERE reference_id = ?", (reference_id,))
        return [_j.loads(str(r["entry_json"]))
                for r in rows]

    def update(self, entry_id: str,
               updates: Dict) -> Optional[dict]:
        import json as _j
        entry = self.get_by_id(entry_id)
        if not entry:
            return None
        entry.update(updates)
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE accounting_registry"
                " SET entry_json = ? WHERE entry_id = ?",
                (_j.dumps(entry, default=str), entry_id))
        return entry

    def delete(self, entry_id: str) -> bool:
        row = self._db.query_one(
            "SELECT entry_id FROM accounting_registry"
            " WHERE entry_id = ?", (entry_id,))
        if not row:
            return False
        self._db.execute(
            "DELETE FROM accounting_registry"
            " WHERE entry_id = ?", (entry_id,))
        return True

    def total_entries(self) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM accounting_registry")
        return int(row["n"]) if row else 0

    def summary(self) -> Dict:
        return {"entries": self.total_entries(),
                "generated_at": self._clock.now()}
