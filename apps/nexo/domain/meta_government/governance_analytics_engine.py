
"""Governance Analytics Engine - analitica de
gobernanza (NG6). Agrega ejecucion presupuestaria y
cumplimiento institucional."""
from __future__ import annotations
from typing import Dict
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class GovernanceAnalyticsEngine:
    """Analitica agregada de gobernanza."""

    def __init__(self, db, clock, registry=None,
                 compliance=None):
        self._db = db
        self._clock = clock
        self._reg = registry
        self._comp = compliance

    def analyze(self, period="") -> Dict:
        from decimal import Decimal as _D
        programs = (self._reg.all_programs()
                    if self._reg is not None
                    else [])
        budgeted = _D("0")
        paid = _D("0")
        by_inst = {}
        for p in programs:
            budgeted = (budgeted
                        + _D(p["budgeted"]))
            paid = paid + _D(p["paid"])
            iid = p["institution_id"]
            by_inst.setdefault(iid, [])
            by_inst[iid].append(p)
        exec_pct = (round(float(paid
                                / budgeted) * 100,
                          2)
                    if budgeted > 0 else 0.0)
        inst_analytics = []
        for iid, plist in by_inst.items():
            pb = sum((_D(p["budgeted"])
                      for p in plist), _D("0"))
            pp = sum((_D(p["paid"])
                      for p in plist), _D("0"))
            rate = (round(float(pp / pb) * 100,
                          2) if pb > 0 else 0.0)
            inst_analytics.append({
                "institution_id": iid,
                "programs": len(plist),
                "execution_pct": rate})
        compliance_avg = None
        if self._comp is not None:
            rates = []
            for iid in by_inst:
                cr = self._comp.compliance_rate(
                    iid)
                rates.append(
                    cr["compliance_rate_pct"])
            compliance_avg = (round(sum(rates)
                                    / len(rates), 2)
                              if rates else 0.0)
        return {"period": period,
                "institutions": len(by_inst),
                "programs": len(programs),
                "total_budgeted":
                    str(budgeted.quantize(
                        _D("0.01"))),
                "total_paid": str(paid.quantize(
                    _D("0.01"))),
                "national_execution_pct":
                    exec_pct,
                "compliance_avg_pct":
                    compliance_avg,
                "by_institution":
                    inst_analytics,
                "generated_at":
                    self._clock.now()}
