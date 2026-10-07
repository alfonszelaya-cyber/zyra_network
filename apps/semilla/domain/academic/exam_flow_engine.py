
"""Exam Flow Engine (S-10) - examenes completos:
calendario + materia + fecha + aviso previo +
resultado + notificacion (compone NotesFlowEngine,
regla 69 — no duplica el flujo de notas).

GARANTIA: sm_calendar se crea aqui IF NOT EXISTS
con el esquema canonico EXACTO del repo (si
CalendarEngine ya la creo, no toca nada)."""
from __future__ import annotations
import inspect as _insp
import uuid
from datetime import date as _date, timedelta
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "exam_canonical_tables", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_calendar (event_id TEXT PRIMARY KEY,"
        " date TEXT NOT NULL, event_type TEXT NOT"
        " NULL, title TEXT NOT NULL, subject TEXT"
        " NOT NULL DEFAULT '', created_at REAL"
        " NOT NULL)",
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

class ExamFlowEngine:
    """Flujo de examenes (S-10)."""

    def __init__(self, db, clock,
                 calendar_engine=None,
                 alert_engine=None,
                 notes_flow=None):
        self._db = db
        self._clock = clock
        self._cal = calendar_engine
        self._alerts = alert_engine
        self._notes = notes_flow
        MigrationRunner(db, "sm.examflow",
                        _MIGRATIONS).run(clock)

    def _plus(self, iso, days) -> str:
        d = _date.fromisoformat(str(iso))
        return str(d
                   + timedelta(days=int(days)))

    def schedule_exam(self, *, date, subject,
                      title, teacher_id="",
                      detail="") -> dict:
        event_id = ("SMCAL-"
                    + uuid.uuid4().hex[:10])
        via = "sql_fallback"
        if self._cal is not None:
            try:
                fn = self._cal.add_event
                kw = _fit_kwargs(fn, {
                    "date": str(date),
                    "event_type": "EXAMEN",
                    "title": str(title),
                    "subject": str(subject)})
                res = fn(**kw)
                if isinstance(res, dict) and \
                        res.get("event_id"):
                    event_id = str(
                        res["event_id"])
                via = "engine"
            except Exception:
                via = "sql_fallback"
        if via == "sql_fallback":
            with self._db.transaction() as cur:
                cur.execute(
                    "INSERT INTO sm_calendar"
                    " (event_id, date,"
                    " event_type, title, subject,"
                    " created_at) VALUES"
                    " (?, ?, 'EXAMEN', ?, ?, ?)",
                    (event_id, str(date),
                     str(title), str(subject),
                     self._clock.now()))
        return {"event_id": event_id,
                "via": via,
                "date": str(date),
                "subject": str(subject)}

    def upcoming_exams(self, *, from_date,
                       horizon_days=7) -> list:
        rows = self._db.query_all(
            "SELECT * FROM sm_calendar WHERE"
            " event_type = 'EXAMEN' AND date >="
            " ? AND date <= ? ORDER BY date,"
            " rowid",
            (str(from_date),
             self._plus(from_date,
                        horizon_days)))
        return [{"event_id":
                     str(r["event_id"]),
                 "date": str(r["date"]),
                 "title": str(r["title"]),
                 "subject": str(r["subject"])}
                for r in rows]

    def notify_upcoming(self, *, from_date,
                        horizon_days=7,
                        student_ids) -> dict:
        exams = self.upcoming_exams(
            from_date=from_date,
            horizon_days=horizon_days)
        ok = 0
        total = 0
        for ex in exams:
            for sid in list(student_ids or []):
                total += 1
                if self._alerts is None:
                    continue
                try:
                    fn = self._alerts.publish
                    kw = _fit_kwargs(fn, {
                        "student_id":
                            str(sid),
                        "alert_type":
                            "EXAMEN_PROXIMO",
                        "message":
                            ("examen de "
                             + ex["subject"]
                             + " el "
                             + ex["date"]),
                        "title":
                            ex["title"],
                        "text":
                            ("examen: "
                             + ex["subject"]),
                        "detail":
                            ex["date"],
                        "severity": "INFO",
                        "source": "S-10"})
                    fn(**kw)
                    ok += 1
                except Exception:
                    pass
        return {"exams": len(exams),
                "alerts_ok": ok,
                "alerts_total": total}

    def record_result(self, *, student_id,
                      subject, period, score,
                      teacher_id="",
                      detail="") -> dict:
        nf = self._notes
        if nf is None:
            from apps.semilla.domain.evaluation.notes_flow_engine import (
                NotesFlowEngine,
            )
            nf = NotesFlowEngine(
                self._db, self._clock)
        return nf.record_note(
            student_id=student_id,
            subject=subject, period=period,
            score=score, teacher_id=teacher_id,
            eval_type="EXAMEN", detail=detail)
