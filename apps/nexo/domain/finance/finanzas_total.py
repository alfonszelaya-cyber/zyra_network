
# finanzas_total.py - NEXO / ZYRA (v7)
from __future__ import annotations
from decimal import Decimal
from typing import Dict
import uuid
from apps.nexo.domain.accounting.accounting_engine import (
    AccountingEngine)
from apps.nexo.domain.finance.declaration_engine import (
    DeclarationEngine)
from apps.nexo.domain.finance.document_fiscal_engine import (
    FiscalDocumentEngine)
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class FinanzasTotal:
    """Agregador financiero supremo."""

    def __init__(self, db: Database, clock: Clock, *,
                 audit=None) -> None:
        self.accounting_engine = AccountingEngine(
            db, clock, audit=audit)
        self.declaration_engine = DeclarationEngine(
            db, clock)
        self.document_engine = FiscalDocumentEngine(
            db, clock)
        self._clock = clock

    def generar_reporte_maestro(self) -> Dict:
        entries = self.accounting_engine.get_entries()
        ingresos = Decimal("0")
        egresos = Decimal("0")
        for entry in entries:
            amount = Decimal(str(entry.get("amount", "0")))
            if entry.get("entry_type") == "CREDIT":
                ingresos += amount
            else:
                egresos += amount
        declaraciones = (
            self.declaration_engine
            .get_all_declarations())
        documentos = (
            self.document_engine
            .get_all_documents())
        ganancia = ingresos - egresos
        return {"report_id": f"FIN-{uuid.uuid4()}",
                "generated_at": self._clock.now(),
                "report_type": "FINANZAS_TOTAL",
                "metricas": {
                    "ingresos": str(ingresos),
                    "egresos": str(egresos),
                    "impuestos": "0",
                    "ganancia_neta": str(ganancia)},
                "declaraciones": len(declaraciones),
                "documentos_fiscales": len(documentos),
                "asientos_contables": len(entries),
                "status": "GENERATED"}

    def dashboard_snapshot(self) -> Dict:
        return self.generar_reporte_maestro()

    def get_summary(self) -> Dict:
        report = self.generar_reporte_maestro()
        return {"report_id": report["report_id"],
                "ganancia_neta": report["metricas"]["ganancia_neta"],
                "declaraciones": report["declaraciones"],
                "documentos": report["documentos_fiscales"],
                "generated_at": report["generated_at"]}
