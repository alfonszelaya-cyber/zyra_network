
"""Teacher Insights - el tutor TAMBIEN ENSENA AL
MAESTRO (SM2). Sin datos de asistencia NO hay
flag 'baja asistencia' (falso positivo eliminado);
CON datos reales si aplica. Informativo (regla 57)."""
from __future__ import annotations
from typing import Dict, List

class TeacherInsightsEngine:
    """Insights docentes sobre su grupo."""

    def __init__(self, evaluation_engine,
                 attendance_engine=None):
        self._eval = evaluation_engine
        self._att = attendance_engine

    def group_report(self, student_ids,
                     subject="") -> Dict:
        report = []
        for sid in student_ids:
            entry = {"student_id": str(sid)}
            avg = (self._eval.average_of(
                sid, subject=subject)
                if subject
                else self._eval.average_of(sid))
            entry["average"] = avg["average"]
            entry["evaluations"] = avg["count"]
            if self._att is not None:
                att = self._att.rate(sid)
                entry["attendance_pct"] = (
                    att["present_rate_pct"])
                entry["attendance_records"] = (
                    att["total"])
            report.append(entry)
        riesgo = []
        for e in report:
            flags = []
            try:
                if float(e["average"]) < 6.0:
                    flags.append("bajo"
                                 " promedio")
            except Exception:
                pass
            tiene_asist = (e.get(
                "attendance_records", 0)
                or 0) > 0
            if (tiene_asist
                    and e.get("attendance_pct")
                    is not None
                    and e["attendance_pct"]
                    < 75.0):
                flags.append("baja asistencia")
            if flags:
                riesgo.append({
                    "student_id":
                        e["student_id"],
                    "flags": flags,
                    "sugerencia":
                        "acompanamiento"
                        " personalizado y"
                        " comunicar al"
                        " encargado"})
        return {"group_size": len(report),
                "students": report,
                "at_risk": riesgo}

    def class_summary(self, student_ids,
                      subject="") -> Dict:
        rep = self.group_report(student_ids,
                                subject)
        vals = []
        for s in rep["students"]:
            try:
                vals.append(float(
                    s["average"]))
            except Exception:
                continue
        if not vals:
            return {"students": 0}
        return {"students": len(vals),
                "group_average":
                    round(sum(vals)
                          / len(vals), 2),
                "at_risk_count":
                    len(rep["at_risk"])}
