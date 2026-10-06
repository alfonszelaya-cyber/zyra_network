
"""Analytics Engine (SM5). Decimal 2d. Promedio
escuela = promedio de promedios por estudiante
(cada alumno cuenta igual)."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import Dict, List
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)

_Q = "0.01"

class AnalyticsEngine:
    """Analitica educativa (Decimal 2d)."""

    def __init__(self, db, clock,
                 evaluation_engine,
                 student_registry=None):
        self._db = db
        self._clock = clock
        self._eval = evaluation_engine
        self._students = student_registry

    def student_report(self, student_id) -> Dict:
        bd = self._eval.subject_breakdown(
            student_id)
        avg = self._eval.average_of(student_id)
        best = (max(bd, key=lambda x: float(
            x["average"])) if bd else None)
        worst = (min(bd, key=lambda x: float(
            x["average"])) if bd else None)
        return {"student_id": student_id,
                "average": avg["average"],
                "evaluations": avg["count"],
                "subjects": bd,
                "best_subject": (best["subject"]
                                 if best
                                 else None),
                "weak_subject": (worst["subject"]
                                 if worst
                                 else None)}

    def school_report(self, student_ids,
                      institution_id) -> Dict:
        from decimal import Decimal as _D
        vals = []
        per_student = []
        for sid in student_ids:
            r = self.student_report(sid)
            try:
                v = float(r["average"])
            except Exception:
                continue
            vals.append(v)
            per_student.append({
                "student_id": sid,
                "average": r["average"],
                "evaluations":
                    r["evaluations"]})
        if vals:
            savg = str((_D(str(sum(vals)))
                        / _D(str(len(vals)))
                        ).quantize(_D(_Q)))
        else:
            savg = "0.00"
        return {"institution_id":
                    institution_id,
                "students": len(vals),
                "school_average": savg,
                "per_student": per_student}

    def national_report(self, institution_ids,
                        student_registry,
                        enrollment_engine=None
                        ) -> Dict:
        from decimal import Decimal as _D
        all_vals = []
        by_inst = []
        for iid in institution_ids:
            students = (student_registry.
                        by_institution(iid))
            ids = [s["student_id"]
                   for s in students]
            rep = self.school_report(
                ids, iid)
            try:
                all_vals.append(float(
                    rep["school_average"]))
            except Exception:
                continue
            by_inst.append(rep)
        if all_vals:
            navg = str((_D(str(sum(all_vals)))
                        / _D(str(len(all_vals)))
                        ).quantize(_D(_Q)))
        else:
            navg = "0.00"
        return {"report": "NATIONAL_EDUCATION",
                "institutions": len(all_vals),
                "national_average": navg,
                "by_institution": by_inst,
                "generated_at":
                    self._clock.now()}
