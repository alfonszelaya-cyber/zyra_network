
# accounting_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(1, "accounting_entries", (
        "CREATE TABLE IF NOT EXISTS accounting_entries ("
        " entry_id TEXT PRIMARY KEY,"
        " account_code TEXT NOT NULL,"
        " amount TEXT NOT NULL,"
        " entry_type TEXT NOT NULL,"
        " description TEXT NOT NULL DEFAULT '',"
        " reference_id TEXT,"
        " metadata_json TEXT NOT NULL DEFAULT '{}',"
        " status TEXT NOT NULL DEFAULT 'POSTED',"
        " created_at REAL NOT NULL)",
    )),
)


class AccountingEngine:
    """Motor central contable (Decimal exacto,
    persistente, auditado por la Red)."""

    def __init__(self, db: Database, clock: Clock,
                 *, audit: AuditTrail) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        MigrationRunner(db, "nexo.accounting", _MIGRATIONS).run(clock)

    def validate_entry(self, account_code: str,
                       amount, entry_type: str) -> bool:
        if not account_code:
            return False
        try:
            Decimal(str(amount))
        except Exception:
            return False
        if Decimal(str(amount)) <= 0:
            return False
        return entry_type in ("DEBIT", "CREDIT")

    def create_entry(self, *, account_code: str, amount,
                     entry_type: str, description: str,
                     reference_id: Optional[str] = None,
                     metadata: Optional[dict] = None) -> dict:
        if not self.validate_entry(account_code, amount, entry_type):
            raise ValueError("Invalid accounting entry")
        amt = Decimal(str(amount))
        entry_id = f"ACC-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO accounting_entries"
                " (entry_id, account_code, amount, entry_type,"
                " description, reference_id, metadata_json,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'POSTED', ?)",
                (entry_id, account_code, str(amt),
                 entry_type, description, reference_id,
                 str(metadata or {}), now))
        self._audit.append(
            event_type="nexo.accounting.entry_created",
            actor="nexo", subject=entry_id,
            payload={"account": account_code,
                     "amount": str(amt),
                     "type": entry_type})
        return {"entry_id": entry_id,
                "account_code": account_code,
                "amount": str(amt),
                "entry_type": entry_type,
                "description": description,
                "reference_id": reference_id,
                "metadata": metadata or {},
                "status": "POSTED",
                "created_at": now}

    def get_entry(self, entry_id: str) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM accounting_entries"
            " WHERE entry_id = ?", (entry_id,))
        return self._row_to_dict(row) if row else None

    def get_entries(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM accounting_entries"
            " ORDER BY created_at")
        return [self._row_to_dict(r) for r in rows]

    def get_entries_by_account(self, account_code: str) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM accounting_entries"
            " WHERE account_code = ? ORDER BY created_at",
            (account_code,))
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row) -> dict:
        return {"entry_id": str(row["entry_id"]),
                "account_code": str(row["account_code"]),
                "amount": str(row["amount"]),
                "entry_type": str(row["entry_type"]),
                "description": str(row["description"]),
                "reference_id": (str(row["reference_id"])
                                 if row["reference_id"] else None),
                "status": str(row["status"]),
                "created_at": float(row["created_at"])}

    def calculate_account_balance(self, account_code: str) -> Decimal:
        total = Decimal("0")
        for e in self.get_entries_by_account(account_code):
            amt = Decimal(e["amount"])
            if e["entry_type"] == "DEBIT":
                total += amt
            else:
                total -= amt
        return total

    def generate_summary(self) -> Dict:
        debits = Decimal("0")
        credits = Decimal("0")
        for e in self.get_entries():
            amt = Decimal(e["amount"])
            if e["entry_type"] == "DEBIT":
                debits += amt
            else:
                credits += amt
        return {"entries": len(self.get_entries()),
                "debits": str(debits),
                "credits": str(credits),
                "generated_at": self._clock.now()}
