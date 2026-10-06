
"""Government Reporting Engine - rendicion de cuentas
(NG6). Reportes de ejecucion presupuestaria por
institucion y periodo + auditorias abiertas."""
from __future__ import annotations
from typing import Dict, List
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

_Q = "0.01"

class GovernmentReportingEngine:
    """Rendicion de cuentas institucional."""

    def __init__(self, db, clock, registry=None,
                 audit=None):
        self._db = db
        self._clock = clock
        self._reg = registry
        self._audit = audit

    def accountability_report(self,
                              institution_id,
                              period) -> Dict:
        from decimal import Decimal as _D
        programs = (self._reg.programs_of(
            institution_id, period)
            if self._reg is not None else [])
        budgeted = _D("0")
        committed = _D("0")
        accrued = _D("0")
        paid = _D("0")
        for p in programs:
            budgeted = (budgeted
                        + _D(p["budgeted"]))
            committed = (committed
                         + _D(p["committed"]))
            accrued = (accrued
                       + _D(p["accrued"]))
            paid = paid + _D(p["paid"])
        q = lambda v: str(v.quantize(_D(_Q)))
        pct = (round(float(paid / budgeted)
                     * 100, 2)
               if budgeted > 0 else 0.0)
        open_audits = (len(self._audit.open_of(
            institution_id))
            if self._audit is not None else 0)
        return {"report_type":
                    "ACCOUNTABILITY_REPORT",
                "institution_id":
                    institution_id,
                "period": period,
                "programs": len(programs),
                "budgeted": q(budgeted),
                "committed": q(committed),
                "accrued": q(accrued),
                "paid": q(paid),
                "execution_pct": pct,
                "open_audits": open_audits,
                "generated_at":
                    self._clock.now()}
