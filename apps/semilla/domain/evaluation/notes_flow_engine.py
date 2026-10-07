
"""Notes Flow Engine (S-9) - la nota como
WORKFLOW: profesor registra -> valida (Decimal
2d, regla 61) -> expediente (sm_evaluations) ->
historial inmutable (fit) -> notificacion al
responsable (FamilyEngine fit; fallback SQL
honesto a sm_family_comms) -> promedio.

GARANTIA: sm_evaluations y sm_family_comms se
crean aqui IF NOT EXISTS con el esquema canonico
EXACTO del repo (si EvaluationEngine/FamilyEngine
ya las crearon, IF NOT EXISTS no toca nada)."""
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
    Migration(1, "notes_canonical_tables", (
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
        "CREATE TABLE IF NOT EXISTS"
        " sm_family_comms (comm_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL,"
        " from_role TEXT NOT NULL, subject TEXT"
        " NOT NULL, body TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL)",
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

class NotesFlowEngine:
    """Flujo de notas (S-9)."""

    def __init__(self, db, clock,
                 evaluation_engine=None,
                 history_engine=None,
                 family_engine=None):
        self._db = db
        self._clock = clock
        self._eval = evaluation_engine
        self._hist = history_engine
        self._fam = family_engine
        MigrationRunner(db, "sm.notesflow",
                        _MIGRATIONS).run(clock)

    def record_note(self, *, student_id, subject,
                    period, score, teacher_id="",
                    eval_type="EXAMEN",
                    detail="") -> dict:
        d = Decimal(str(score)).quantize(
            Decimal("0.01"))
        if not (Decimal("0.00") <= d
                <= Decimal("10.00")):
            raise ValueError(
                "score fuera de rango 0..10")
        score_s = str(d)
        eval_id = ("SMEV-"
                   + uuid.uuid4().hex[:10])
        via = "sql_fallback"
        if self._eval is not None:
            try:
                fn = self._eval.register
                kw = _fit_kwargs(fn, {
                    "student_id":
                        str(student_id),
                    "subject": str(subject),
                    "period": str(period),
                    "score": score_s,
                    "scale_max": "10.00",
                    "eval_type":
                        str(eval_type),
                    "teacher_id":
                        str(teacher_id),
                    "detail": str(detail)})
                res = fn(**kw)
                if isinstance(res, dict) and \
                        res.get("evaluation_id"):
                    eval_id = str(
                        res["evaluation_id"])
                via = "engine"
            except Exception:
                via = "sql_fallback"
        if via == "sql_fallback":
            with self._db.transaction() as cur:
                cur.execute(
                    "INSERT INTO"
                    " sm_evaluations"
                    " (evaluation_id, student_id,"
                    " subject, period, score,"
                    " scale_max, eval_type,"
                    " teacher_id, detail,"
                    " created_at) VALUES"
                    " (?, ?, ?, ?, ?, '10.00',"
                    " ?, ?, ?, ?)",
                    (eval_id,
                     str(student_id),
                     str(subject),
                     str(period), score_s,
                     str(eval_type),
                     str(teacher_id),
                     str(detail),
                     self._clock.now()))
        hist_ok = False
        if self._hist is not None:
            try:
                fn = self._hist.append
                kw = _fit_kwargs(fn, {
                    "student_id":
                        str(student_id),
                    "event_type":
                        "NOTA_REGISTRADA",
                    "detail":
                        (str(subject) + " "
                         + str(period) + ": "
                         + score_s)})
                fn(**kw)
                hist_ok = True
            except Exception:
                hist_ok = False
        notified = False
        comm_id = ""
        subj_msg = ("Nueva nota " + str(subject)
                    + " (" + str(period)
                    + "): " + score_s)
        if self._fam is not None:
            try:
                fn = \
                    self._fam.send_communication
                kw = _fit_kwargs(fn, {
                    "student_id":
                        str(student_id),
                    "from_role": "PROFESOR",
                    "subject": subj_msg,
                    "body":
                        ("nota registrada por "
                         + str(teacher_id
                               or "sistema"))})
                res = fn(**kw)
                if isinstance(res, dict) and \
                        res.get("comm_id"):
                    comm_id = str(
                        res["comm_id"])
                notified = True
            except Exception:
                notified = False
        if not notified:
            comm_id = ("SMCOM-"
                       + uuid.uuid4()
                       .hex[:10])
            with self._db.transaction() as cur:
                cur.execute(
                    "INSERT INTO"
                    " sm_family_comms"
                    " (comm_id, student_id,"
                    " from_role, subject, body,"
                    " created_at) VALUES"
                    " (?, ?, 'PROFESOR', ?, ?,"
                    " ?)",
                    (comm_id,
                     str(student_id),
                     subj_msg,
                     ("nota registrada por "
                      + str(teacher_id
                            or "sistema")),
                     self._clock.now()))
            notified = True
        return {"evaluation_id": eval_id,
                "score": score_s,
                "via": via,
                "history_ok": hist_ok,
                "notified": notified,
                "comm_id": comm_id}

    def average_of(self, student_id):
        rows = self._db.query_all(
            "SELECT score FROM sm_evaluations"
            " WHERE student_id = ?",
            (str(student_id),))
        if not rows:
            return None
        tot = Decimal("0")
        n = 0
        for r in rows:
            try:
                tot += Decimal(str(r["score"]))
                n += 1
            except Exception:
                pass
        if n == 0:
            return None
        return str((tot / Decimal(n)).quantize(
            Decimal("0.01")))
