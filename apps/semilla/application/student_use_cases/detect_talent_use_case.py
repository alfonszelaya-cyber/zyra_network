
"""Detect Talent Use Case (SM3). execute DENTRO
de la clase."""
from __future__ import annotations


class DetectTalentUseCase:
    """Escanea el desglose por materia y registra
    talentos con promedio >= min_average."""

    def __init__(self, evaluation_engine,
                 talent_engine,
                 min_average="9.00"):
        self._eval = evaluation_engine
        self._tal = talent_engine
        self._min = str(min_average)

    def execute(self, *, student_id) -> dict:
        breakdown = (self._eval
                     .subject_breakdown(
                         student_id))
        detectados = []
        for row in breakdown:
            try:
                if (float(row["average"])
                        >= float(self._min)):
                    t = (self._tal.
                         register_talent(
                             student_id=student_id,
                             category=row["subject"],
                             detail=("promedio "
                                     + row["average"]),
                             source="USE_CASE",
                             score=row["average"]))
                    detectados.append(t)
            except Exception:
                continue
        return {"student_id": student_id,
                "threshold": self._min,
                "talents_registered":
                    len(detectados),
                "talents": detectados}
