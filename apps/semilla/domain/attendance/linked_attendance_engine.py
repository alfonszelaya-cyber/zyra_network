
"""Linked Attendance Engine (S-6) - asistencia POR
CLASE vinculada: estudiante + aula + materia +
profesor + fecha + hora. Detecta 'entro a la
escuela pero no entro a Matematicas' y alerta.

La tabla canonica sm_attendance es DIARIA
(UNIQUE(student_id, date)): esta es la capa POR
CLASE (sm_class_attendance) y delega el registro
diario al AttendanceEngine existente (fit
defensivo — regla 69)."""
from __future__ import annotations
import inspect as _insp
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_class_attendance", (
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

class LinkedAttendanceEngine:
    """Asistencia por clase vinculada (S-6)."""

    def __init__(self, db, clock,
                 attendance_engine=None,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._att = attendance_engine
        self._alerts = alert_engine
        MigrationRunner(db, "sm.classatt",
                        _MIGRATIONS).run(clock)

    def record_class(self, *, student_id,
                     classroom_id, subject, date,
                     status, time_slot="",
                     teacher_id="",
                     detail="") -> dict:
        aid = "SMCLA-" + uuid.uuid4().hex[:10]
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO"
                " sm_class_attendance"
                " (class_att_id, student_id,"
                " classroom_id, subject, date,"
                " time_slot, status, teacher_id,"
                " detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?)",
                (aid, str(student_id),
                 str(classroom_id),
                 str(subject), str(date),
                 str(time_slot), str(status),
                 str(teacher_id), str(detail),
                 self._clock.now()))
        daily_ok = False
        if self._att is not None:
            try:
                fn = self._att.record
                kw = _fit_kwargs(fn, {
                    "student_id":
                        str(student_id),
                    "date": str(date),
                    "status": str(status),
                    "present":
                        (str(status)
                         == "PRESENTE"),
                    "recorded_by":
                        (str(teacher_id)
                         or "sistema"),
                    "detail": str(detail)})
                fn(**kw)
                daily_ok = True
            except Exception:
                daily_ok = False
        return {"class_att_id": aid,
                "daily_delegated": daily_ok}

    def missing_subjects(self, *, student_id,
                         classroom_id, date
                         ) -> list:
        rows = self._db.query_all(
            "SELECT DISTINCT subject FROM"
            " sm_class_attendance WHERE"
            " classroom_id = ? AND date = ?",
            (str(classroom_id), str(date)))
        dadas = set(str(r["subject"])
                    for r in rows)
        mias = self._db.query_all(
            "SELECT DISTINCT subject FROM"
            " sm_class_attendance WHERE"
            " student_id = ? AND classroom_id ="
            " ? AND date = ?",
            (str(student_id),
             str(classroom_id), str(date)))
        mias_set = set(str(r["subject"])
                       for r in mias)
        return sorted(dadas - mias_set)

    def campus_gap_alert(self, *, student_id,
                         classroom_id, date,
                         was_on_campus,
                         alert_type=
                         "CLASE_SIN_REGISTRO"
                         ) -> dict:
        ms = self.missing_subjects(
            student_id=student_id,
            classroom_id=classroom_id,
            date=date)
        if not was_on_campus or not ms:
            return {"missing": ms,
                    "alerted": False,
                    "note": ("alumno no estuvo"
                             " en la escuela"
                             if not was_on_campus
                             else "sin materias"
                                  " faltantes")}
        alerted = False
        if self._alerts is not None:
            try:
                fn = self._alerts.publish
                kw = _fit_kwargs(fn, {
                    "student_id":
                        str(student_id),
                    "alert_type":
                        str(alert_type),
                    "message":
                        ("entro a la escuela"
                         " pero no registro"
                         " clase de: "
                         + ", ".join(ms)),
                    "title":
                        "clase sin registro",
                    "text":
                        ", ".join(ms),
                    "detail":
                        ("aula "
                         + str(classroom_id)
                         + " dia " + str(date)),
                    "severity": "MEDIA",
                    "source": "S-6"})
                fn(**kw)
                alerted = True
            except Exception:
                alerted = False
        return {"missing": ms,
                "alerted": alerted}
