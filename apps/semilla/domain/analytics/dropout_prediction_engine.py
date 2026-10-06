
"""Dropout Prediction (SM4). Informativo (57)."""
from __future__ import annotations
from typing import Dict

class DropoutPredictionEngine:
    """Riesgo de abandono escolar (informativo)."""

    def __init__(self, attendance_engine,
                 evaluation_engine,
                 emotional_engine=None):
        self._att = attendance_engine
        self._eval = evaluation_engine
        self._emo = emotional_engine

    def assess(self, student_id) -> Dict:
        factors = []
        risk = "LOW"
        rank = {"LOW": 0, "MEDIUM": 1,
                "HIGH": 2}
        att_pct = None
        att = self._att.rate(student_id)
        if att["total"] > 0:
            att_pct = (att
                       ["present_rate_pct"])
        avg_val = None
        avg = self._eval.average_of(student_id)
        if avg["count"] > 0:
            avg_val = float(avg["average"])
        emo_level = None
        if self._emo is not None:
            st = self._emo.emotional_state(
                student_id)
            if st["records"]:
                emo_level = (st
                             ["current_level"])
        if (att_pct is None and avg_val is None
                and emo_level is None):
            return {"student_id": student_id,
                    "risk_level":
                        "INSUFFICIENT_DATA",
                    "factors": [],
                    "recommendation":
                        "sin datos suficientes"
                        " para evaluar"}
        if att_pct is not None:
            if att_pct < 70.0:
                factors.append(
                    "asistencia critica ("
                    + str(att_pct) + "%)")
                risk = "HIGH"
            elif att_pct < 85.0:
                factors.append(
                    "asistencia baja ("
                    + str(att_pct) + "%)")
                if rank["MEDIUM"] > rank[risk]:
                    risk = "MEDIUM"
        if avg_val is not None:
            if avg_val < 5.0:
                factors.append(
                    "promedio critico ("
                    + str(avg_val) + ")")
                risk = "HIGH"
            elif avg_val < 7.0:
                factors.append(
                    "promedio bajo ("
                    + str(avg_val) + ")")
                if rank["MEDIUM"] > rank[risk]:
                    risk = "MEDIUM"
        if emo_level == "CRITICAL":
            factors.append(
                "alerta emocional critica")
            risk = "HIGH"
        elif emo_level == "ALERT":
            factors.append("alerta emocional")
            if rank["MEDIUM"] > rank[risk]:
                risk = "MEDIUM"
        return {"student_id": student_id,
                "risk_level": risk,
                "factors": factors,
                "attendance_pct": att_pct,
                "average": avg_val,
                "emotional_state": emo_level,
                "recommendation":
                    ("acompanamiento inmediato:"
                     " contactar al encargado"
                     " y activar apoyo"
                     if risk == "HIGH" else
                     "dar seguimiento cercano"
                     if risk == "MEDIUM" else
                     "sin riesgo detectado")}
