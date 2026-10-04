
# balance_engine.py - NEXO / ZYRA (migrado mejorado v3)
from __future__ import annotations

from decimal import Decimal

from typing import Dict, List, Optional
import uuid

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(1, "balance_records", (
        "CREATE TABLE IF NOT EXISTS balance_records ("
        " balance_id TEXT PRIMARY KEY,"
        " total_debits TEXT NOT NULL,"
        " total_credits TEXT NOT NULL,"
        " net_balance TEXT NOT NULL,"
        " generated_at REAL NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'CALCULATED')",
    )),
)


class BalanceEngine:
    """Motor de balances contables (Decimal)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.balance",
                        _MIGRATIONS).run(clock)

    def calculate_balance(self, entries: List[dict]) -> dict:
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for entry in entries:
            et = entry.get("entry_type", "")
            amt = Decimal(str(entry.get("amount", "0")))
            if et == "DEBIT":
                total_debits += amt
            elif et == "CREDIT":
                total_credits += amt
        balance_id = f"BAL-{uuid.uuid4()}"
        now = self._clock.now()
        neto = total_debits - total_credits
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO balance_records"
                " (balance_id, total_debits,"
                " total_credits, net_balance,"
                " generated_at, status)"
                " VALUES (?, ?, ?, ?, ?, 'CALCULATED')",
                (balance_id, str(total_debits),
                 str(total_credits), str(neto), now))
        return {"balance_id": balance_id,
                "total_debits": str(total_debits),
                "total_credits": str(total_credits),
                "net_balance": str(neto),
                "generated_at": now,
                "status": "CALCULATED"}

    def get_balances(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM balance_records"
            " ORDER BY generated_at")
        return [{"balance_id": str(r["balance_id"]),
                 "total_debits": str(r["total_debits"]),
                 "total_credits": str(r["total_credits"]),
                 "net_balance": str(r["net_balance"]),
                 "generated_at": float(r["generated_at"]),
                 "status": str(r["status"])}
                for r in rows]

    def get_last_balance(self) -> Optional[dict]:
        bs = self.get_balances()
        return bs[-1] if bs else None

    def generate_balance_report(self) -> Dict:
        return {"balances_generated":
                len(self.get_balances()),
                "latest_balance": self.get_last_balance(),
                "generated_at": self._clock.now()}
