
# Zyra_finance_master.py - NEXO / ZYRA (v7)
from __future__ import annotations
from decimal import Decimal
from typing import Dict
import uuid
from apps.nexo.domain.accounting.accounting_engine import (
    AccountingEngine)
from apps.nexo.domain.accounting.balance_engine import (
    BalanceEngine)
from apps.nexo.domain.accounting.journal_engine import (
    JournalEngine)
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class ZyraFinanceMaster:
    """Motor Financiero Maestro."""

    def __init__(self, db: Database, clock: Clock, *,
                 audit=None) -> None:
        self.accounting_engine = AccountingEngine(
            db, clock, audit=audit)
        self.balance_engine = BalanceEngine(db, clock)
        self.journal_engine = JournalEngine(db, clock)
        self._clock = clock

    def generar_reporte_maestro(self) -> Dict:
        entries = self.accounting_engine.get_entries()
        revenue = Decimal("0")
        expenses = Decimal("0")
        for entry in entries:
            amount = Decimal(str(entry.get("amount", "0")))
            if entry.get("entry_type") == "CREDIT":
                revenue += amount
            else:
                expenses += amount
        profit = revenue - expenses
        return {"report_id": f"FIN-{uuid.uuid4()}",
                "generated_at": self._clock.now(),
                "report_type": "MASTER_FINANCIAL",
                "revenue": str(revenue),
                "expenses": str(expenses),
                "profit": str(profit),
                "total_entries": len(entries),
                "status": "GENERATED"}

    def dashboard_snapshot(self) -> Dict:
        return self.generar_reporte_maestro()

    def summary(self) -> Dict:
        report = self.generar_reporte_maestro()
        return {"report_id": report["report_id"],
                "profit": report["profit"],
                "entries": report["total_entries"],
                "generated_at": report["generated_at"]}
