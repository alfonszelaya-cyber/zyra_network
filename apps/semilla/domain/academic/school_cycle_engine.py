
"""School Cycle Engine (S-5) - el ciclo escolar
como UN solo flujo: matricula -> asignacion ->
clases -> asistencia -> notas -> promocion ->
siguiente ano (MISMA persona, MISMO expediente).

Orquesta engines existentes (regla 69):
StudentRegistryEngine.promote (firma verificada),
EnrollmentEngine.enroll (verificada),
AcademicHistoryEngine.append (fit defensivo).
Tablas propias: sm_cycle_years, sm_cycle_events.
GARANTIA: sm_evaluations se crea aqui IF NOT
EXISTS con el esquema canonico EXACTO del repo
(state_of la consulta; si EvaluationEngine ya la
creo, IF NOT EXISTS no toca nada)."""
from __future__ import annotations
import inspect as _insp
import uuid
from decimal import Decimal
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "cycle", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_cycle_years (year_id TEXT PRIMARY"
        " KEY, institution_id TEXT NOT NULL,"
        " school_year TEXT NOT NULL, start_date"
        " TEXT NOT NULL DEFAULT '', end_date TEXT"
        " NOT NULL DEFAULT '', status TEXT NOT"
        " NULL DEFAULT 'ACTIVO', created_at REAL"
        " NOT NULL, UNIQUE(institution_id,"
        " school_year))",
        "CREATE TABLE IF NOT EXISTS"
        " sm_cycle_events (event_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL,"
        " event_type TEXT NOT NULL, school_year"
        " TEXT NOT NULL DEFAULT '', detail TEXT"
        " NOT NULL DEFAULT '', created_at REAL"
        " NOT NULL)",
    )),
    Migration(2, "cycle_canonical_tables", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_evaluations (evaluation_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, period TEXT NOT"
        " NULL, score TEXT NOT NULL, scale_max"
        " TEXT NOT NULL DEFAULT '10.00',"
        " eval_type TEXT NOT NULL DEFAULT"
        " 'EXAMEN', teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL)",
    )),
)

_PK = _insp.Parameter

def _fit_kwargs(func, desired):
    """Solo pasa los kwargs que la firma REAL
    acepta. ValueError si falta un requerido."""
    try:
        params = _insp.signature(
            func).parameters
    except (TypeError, ValueError):
        return dict(desired)
    if any(p.kind == _PK.VAR_KEYWORD
           for p in params.values()):
        return dict(desired)
    ok = set()
    for n, p in params.items():
        if p.kind in (_PK.POSITIONAL_OR_KEYWORD,
                      _PK.KEYWORD_ONLY):
            ok.add(n)
    res = {k: v for k, v in desired.items()
           if k in ok}
    for n, p in params.items():
        if (n != "self" and n not in res
                and p.default is _PK.empty
                and p.kind in (
                    _PK.POSITIONAL_OR_KEYWORD,
                    _PK.KEYWORD_ONLY)):
            raise ValueError(
                "firma incompatible: falta "
                + str(n))
    return res

class SchoolCycleEngine:
    """Ciclo escolar unico (S-5)."""

    def __init__(self, db, clock,
                 student_registry,
                 enrollment_engine,
                 history_engine=None):
        self._db = db
        self._clock = clock
        self._students = student_registry
        self._enr = enrollment_engine
        self._hist = history_engine
        MigrationRunner(db, "sm.cycle",
                        _MIGRATIONS).run(clock)

    def open_year(self, *, institution_id,
                  school_year, start_date="",
                  end_date="") -> dict:
        yid = (str(institution_id) + "|"
               + str(school_year))
        self._db.execute(
            "INSERT OR REPLACE INTO"
            " sm_cycle_years (year_id,"
            " institution_id, school_year,"
            " start_date, end_date, status,"
            " created_at) VALUES (?, ?, ?, ?, ?,"
            " 'ACTIVO', ?)",
            (yid, str(institution_id),
             str(school_year),
             str(start_date), str(end_date),
             self._clock.now()))
        return {"year_id": yid,
                "institution_id":
                    str(institution_id),
                "school_year": str(school_year),
                "status": "ACTIVO"}

    def _log_event(self, student_id, event_type,
                   school_year, detail):
        eid = "SMCYC-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO sm_cycle_events"
            " (event_id, student_id, event_type,"
            " school_year, detail, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (eid, str(student_id),
             str(event_type),
             str(school_year), str(detail),
             self._clock.now()))
        return eid

    def _history_ok(self, student_id, event_type,
                    detail) -> bool:
        if self._hist is None:
            return False
        try:
            fn = self._hist.append
            kw = _fit_kwargs(fn, {
                "student_id": str(student_id),
                "event_type": str(event_type),
                "detail": str(detail)})
            fn(**kw)
            return True
        except Exception:
            return False

    def promote_student(self, *, student_id,
                        new_level, new_grade,
                        actor="") -> dict:
        est = self._students.promote(
            str(student_id), str(new_level),
            str(new_grade))
        detail = ("promocion a " + str(new_level)
                  + " " + str(new_grade)
                  + " por " + str(actor or
                                  "sistema"))
        hok = self._history_ok(
            student_id, "PROMOCION", detail)
        eid = self._log_event(
            student_id, "PROMOCION", "2026",
            detail)
        return {"promoted": True,
                "student": est,
                "cycle_event_id": eid,
                "history_ok": hok}

    def close_and_reenroll(self, *, student_id,
                           new_level, new_grade,
                           classroom_id_next,
                           next_school_year,
                           actor="") -> dict:
        prom = self.promote_student(
            student_id=student_id,
            new_level=new_level,
            new_grade=new_grade, actor=actor)
        enr = self._enr.enroll(
            student_id=str(student_id),
            classroom_id=str(classroom_id_next),
            school_year=str(next_school_year))
        self._log_event(
            student_id, "RE_MATRICULA",
            str(next_school_year),
            "mismo expediente, nuevo ano")
        return {"promoted": True,
                "student": prom["student"],
                "enrollment": enr,
                "same_expediente": True,
                "student_id": str(student_id)}

    def state_of(self, student_id) -> dict:
        est = self._students.get(str(student_id))
        rows = self._db.query_all(
            "SELECT score FROM sm_evaluations"
            " WHERE student_id = ?",
            (str(student_id),))
        notas = []
        for r in rows:
            try:
                notas.append(
                    Decimal(str(r["score"])))
            except Exception:
                pass
        prom = (str((sum(notas)
                     / Decimal(len(notas)))
                    .quantize(Decimal("0.01")))
                if notas else None)
        n_ev = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sm_cycle_events WHERE student_id"
            " = ?", (str(student_id),))
        n_enr = None
        try:
            lst = self._enr.enrollments_of(
                str(student_id))
            n_enr = len(tuple(lst or ()))
        except Exception:
            n_enr = None
        return {"student": est,
                "promedio": prom,
                "notas_count": len(notas),
                "enrollments": n_enr,
                "cycle_events":
                    int(n_ev["n"])
                    if n_ev else 0}
