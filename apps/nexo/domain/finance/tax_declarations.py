
# tax_declarations.py - NEXO / ZYRA (v7)
from __future__ import annotations
from decimal import Decimal
from typing import Dict, List, Optional
from apps.nexo.domain.accounting.accounting_engine import (
    AccountingEngine)
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class TaxDeclarationsEngine:
    """Motor Fiscal (Decimal)."""

    def __init__(self, db: Database, clock: Clock, *,
                 accounting_engine: AccountingEngine = None,
                 audit=None) -> None:
        self.accounting_engine = (
            accounting_engine
            or AccountingEngine(
                db, clock, audit=audit))
        self._db = db
        self._clock = clock

    def calcular_acumulados(self,
                            company_id: Optional[str] = None) -> Dict:
        ingresos = Decimal("0")
        gastos = Decimal("0")
        for entry in self.accounting_engine.get_entries():
            amount = Decimal(str(entry.get("amount", "0")))
            if entry.get("entry_type") == "CREDIT":
                ingresos += amount
            else:
                gastos += amount
        utilidad = ingresos - gastos
        return {"ingresos": str(ingresos),
                "gastos": str(gastos),
                "utilidad": str(utilidad)}

    def generar_declaracion_mensual(self, *,
        company_id: str, jurisdiction: str,
        month: int, year: int) -> Dict:
        acumulados = self.calcular_acumulados(company_id)
        return {"declaration_id": f"TAX-{month}-{year}-{company_id}",
                "company_id": company_id,
                "jurisdiction": jurisdiction,
                "month": month, "year": year,
                "acumulados": acumulados,
                "status": "GENERATED",
                "created_at": self._clock.now()}

    def get_summary(self) -> Dict:
        return {"generated_at": self._clock.now()}
