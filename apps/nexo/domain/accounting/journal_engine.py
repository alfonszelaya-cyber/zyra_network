
"""Libro Diario contable persistente.

N-1: si el asiento trae 'lines', se valida el
cuadre (sum DEBIT == sum CREDIT) antes de
registrarse. La pierna individual se acepta como
registro, pero el asiento OFICIAL va cuadrado."""
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
    Migration(1, "journal_entries", (
        "CREATE TABLE IF NOT EXISTS journal_entries ("
        " journal_id TEXT PRIMARY KEY,"
        " entry_json TEXT NOT NULL,"
        " registered_at REAL NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'POSTED')",
    )),
)


class JournalEngine:
    """Libro Diario contable persistente."""

    def __init__(self, db: Database, clock: Clock,
                 *, outbox=None) -> None:
        self._db = db
        self._clock = clock
        self._outbox = outbox
        MigrationRunner(db, "nexo.journal", _MIGRATIONS).run(clock)

    def register_entry(self, accounting_entry: dict) -> dict:
        import json as _json
        from decimal import Decimal as _D
        lines = accounting_entry.get("lines")
        if lines:
            td = sum((_D(str(l.get("amount", "0")))
                      for l in lines
                      if str(l.get("entry_type", ""))
                      .upper() == "DEBIT"), _D("0"))
            tc = sum((_D(str(l.get("amount", "0")))
                      for l in lines
                      if str(l.get("entry_type", ""))
                      .upper() == "CREDIT"), _D("0"))
            if td != tc:
                raise ValueError(
                    "asiento descuadrado en journal:"
                    " DEBIT=" + str(td) + " CREDIT="
                    + str(tc))
        journal_id = f"JRN-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO journal_entries"
                " (journal_id, entry_json,"
                " registered_at, status)"
                " VALUES (?, ?, ?, 'POSTED')",
                (journal_id,
                 _json.dumps(accounting_entry, default=str),
                 now))
        return {"journal_id": journal_id,
                "entry": accounting_entry,
                "registered_at": now,
                "status": "POSTED"}

    def get_entries(self) -> List[dict]:
        import json as _json
        rows = self._db.query_all(
            "SELECT * FROM journal_entries"
            " ORDER BY registered_at")
        out = []
        for r in rows:
            out.append({
                "journal_id": str(r["journal_id"]),
                "entry": _json.loads(str(r["entry_json"])),
                "registered_at": float(r["registered_at"]),
                "status": str(r["status"])})
        return out

    def get_entry(self, journal_id: str) -> Optional[dict]:
        for item in self.get_entries():
            if item["journal_id"] == journal_id:
                return item
        return None

    def get_entries_by_account(self, account_code: str) -> List[dict]:
        return [i for i in self.get_entries()
                if (i.get("entry", {}).get(
                    "account_code") == account_code)]

    def get_entries_by_reference(self, reference_id: str) -> List[dict]:
        return [i for i in self.get_entries()
                if (i.get("entry", {}).get(
                    "reference_id") == reference_id)]

    def generate_journal_report(self) -> Dict:
        debit_count = 0
        credit_count = 0
        for item in self.get_entries():
            et = (item.get("entry", {}).get(
                "entry_type", ""))
            if et == "DEBIT":
                debit_count += 1
            elif et == "CREDIT":
                credit_count += 1
        return {"journal_entries": len(self.get_entries()),
                "debit_entries": debit_count,
                "credit_entries": credit_count,
                "generated_at": self._clock.now()}

    def generate_metrics(self) -> Dict:
        return {"entries": len(self.get_entries()),
                "generated_at": self._clock.now()}
