
"""Education Core Engine (S-11 / zyra_education_core)
- indicadores educativos consolidados POR
INSTITUCION (lectura pura, sin duplicar motores):
alumnos, aulas/capacidad/cupos por turno,
promedios por materia, asistencia y LISTA DE
RIESGO (promedio < 6.00 o asistencia < 70%).

Es la semilla de la Capa A de GOV-DATA
(APP_OPERATIONAL_INTELLIGENCE): cada app publica
sus indicadores; el panel nacional los agrega.

Regla 61: promedios/ratios Decimal 2d.
Regla 76: ORDER BY rowid/subject."""
from __future__ import annotations
from decimal import Decimal
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "core_guarantees", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_evaluations (evaluation_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, period TEXT NOT"
        " NULL, score TEXT NOT NULL, scale_max"
        " TEXT NOT NULL DEFAULT '10.00',"
        " eval_type TEXT NOT NULL DEFAULT"
        " 'EXAMEN', teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL DEFAULT"
        " '', created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_class_attendance (class_att_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " classroom_id TEXT NOT NULL, subject TEXT"
        " NOT NULL, date TEXT NOT NULL, time_slot"
        " TEXT NOT NULL DEFAULT '', status TEXT"
        " NOT NULL, teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL DEFAULT"
        " '', created_at REAL NOT NULL,"
        " UNIQUE(student_id, classroom_id, subject,"
        " date, time_slot))",
    )),
)


def _q2(x) -> str:
    return str(Decimal(str(x)).quantize(
        Decimal("0.01")))


class EducationCoreEngine:
    """Indicadores por institucion (Capa A)."""

    def __init__(self, db, clock,
                 student_registry):
        self._db = db
        self._clock = clock
        self._students = student_registry
        MigrationRunner(db, "sm.educore",
                        _MIGRATIONS).run(clock)

    def indicators(self, institution_id,
                   school_year="2026") -> dict:
        students = list(
            self._students.by_institution(
                str(institution_id)))
        ids = [str(s["student_id"])
               for s in students]
        rooms = self._db.query_all(
            "SELECT capacity, enrolled, turn FROM"
            " sm_classrooms WHERE institution_id"
            " = ? AND school_year = ?",
            (str(institution_id),
             str(school_year)))
        aulas = len(rooms)
        cap = sum(int(r["capacity"] or 0)
                  for r in rooms)
        enr = sum(int(r["enrolled"] or 0)
                  for r in rooms)
        por_turno = {}
        for r in rooms:
            t = str(r["turn"] or "SIN_TURNO")
            e = por_turno.setdefault(
                t, {"capacidad": 0,
                    "matriculados": 0})
            e["capacidad"] += int(
                r["capacity"] or 0)
            e["matriculados"] += int(
                r["enrolled"] or 0)
        avgs = {}
        rows = self._db.query_all(
            "SELECT e.subject AS subject,"
            " AVG(CAST(e.score AS REAL)) AS a"
            " FROM sm_evaluations e JOIN"
            " sm_students s ON e.student_id ="
            " s.student_id WHERE"
            " s.institution_id = ? GROUP BY"
            " e.subject ORDER BY e.subject",
            (str(institution_id),))
        for r in rows:
            if r["a"] is not None:
                avgs[str(r["subject"])] = \
                    _q2(r["a"])
        att_rows = self._db.query_all(
            "SELECT a.status AS status,"
            " COUNT(*) AS n FROM"
            " sm_class_attendance a JOIN"
            " sm_students s ON a.student_id ="
            " s.student_id WHERE"
            " s.institution_id = ? GROUP BY"
            " a.status",
            (str(institution_id),))
        att = {str(r["status"]): int(r["n"])
               for r in att_rows}
        tot_att = sum(att.values())
        pres = att.get("PRESENTE", 0)
        ratio = (_q2(Decimal(pres)
                     * Decimal(100)
                     / Decimal(tot_att))
                 if tot_att else None)
        riesgo = []
        for sid in ids:
            r1 = self._db.query_one(
                "SELECT AVG(CAST(score AS REAL))"
                " AS a FROM sm_evaluations WHERE"
                " student_id = ?", (sid,))
            r2 = self._db.query_all(
                "SELECT status, COUNT(*) AS n"
                " FROM sm_class_attendance WHERE"
                " student_id = ? GROUP BY status",
                (sid,))
            a = (r1["a"]
                 if r1 else None)
            p = sum(int(x["n"])
                    for x in r2
                    if x["status"]
                    == "PRESENTE")
            tt = sum(int(x["n"]) for x in r2)
            reasons = []
            if a is not None and \
                    Decimal(str(a)) \
                    < Decimal("6.00"):
                reasons.append(
                    "promedio " + _q2(a))
            if tt > 0:
                pct = (Decimal(p)
                       * Decimal(100)
                       / Decimal(tt))
                if pct < Decimal("70.00"):
                    reasons.append(
                        "asistencia "
                        + _q2(pct) + "%")
            if reasons:
                riesgo.append({
                    "student_id": sid,
                    "reasons": reasons})
        return {"institution_id":
                    str(institution_id),
                "school_year":
                    str(school_year),
                "alumnos": len(ids),
                "aulas": aulas,
                "capacidad": cap,
                "matriculados": enr,
                "cupos": cap - enr,
                "por_turno": por_turno,
                "promedios": avgs,
                "asistencia": att,
                "asistencia_pct": ratio,
                "riesgo": riesgo}
