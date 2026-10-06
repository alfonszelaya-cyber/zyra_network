
"""Evaluation Engine - evaluaciones (SM1)."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "sm_evaluations", (
        "CREATE TABLE IF NOT EXISTS sm_evaluations (evaluation_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, subject TEXT NOT NULL, period TEXT NOT NULL, score TEXT NOT NULL, scale_max TEXT NOT NULL DEFAULT '10.00', eval_type TEXT NOT NULL DEFAULT 'EXAMEN', teacher_id TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class EvaluationEngine:
    """Notas y evaluaciones (Decimal 2d)."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.eval",
                        _MIGRATIONS).run(clock)

    def register(self, *, student_id, subject,
                 period, score, eval_type="EXAMEN",
                 teacher_id="", detail="") -> dict:
        val = _D(str(score)).quantize(
            _D(_Q), rounding=_UP)
        mx = _D("10.00")
        if val < 0 or val > mx:
            raise ValueError(
                "score fuera de escala 0-10")
        if not str(subject).strip():
            raise ValueError(
                "subject requerido")
        eid = "SMEVL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_evaluations"
                " (evaluation_id, student_id,"
                " subject, period, score,"
                " scale_max, eval_type,"
                " teacher_id, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?)",
                (eid, student_id,
                 str(subject).strip(), period,
                 str(val), str(mx),
                 str(eval_type),
                 str(teacher_id),
                 str(detail), now))
        if self._alerts is not None:
            self._alerts.publish(
                student_id=student_id,
                alert_type="GRADE_POSTED",
                title="Nueva calificacion: "
                      + str(subject),
                detail=("Nota " + str(val)
                        + " en " + period),
                recipient_role="PARENT")
        return self.get(eid)

    def get(self, evaluation_id
            ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_evaluations WHERE"
            " evaluation_id = ?",
            (evaluation_id,))
        if not row:
            return None
        return {"evaluation_id":
                    str(row["evaluation_id"]),
                "student_id":
                    str(row["student_id"]),
                "subject": str(row["subject"]),
                "period": str(row["period"]),
                "score": str(_D(
                    str(row["score"]))
                    .quantize(_D(_Q))),
                "eval_type":
                    str(row["eval_type"]),
                "teacher_id":
                    str(row["teacher_id"])}

    def average_of(self, student_id,
                   subject="",
                   period="") -> dict:
        if subject and period:
            rows = self._db.query_all(
                "SELECT score FROM"
                " sm_evaluations WHERE"
                " student_id = ? AND subject = ?"
                " AND period = ?",
                (student_id, subject, period))
        elif subject:
            rows = self._db.query_all(
                "SELECT score FROM"
                " sm_evaluations WHERE"
                " student_id = ? AND subject = ?",
                (student_id, subject))
        else:
            rows = self._db.query_all(
                "SELECT score FROM"
                " sm_evaluations WHERE"
                " student_id = ?", (student_id,))
        if not rows:
            return {"count": 0,
                    "average": "0.00"}
        total = _D("0")
        for r in rows:
            total = total + _D(str(r["score"]))
        avg = (total / _D(str(len(rows)))
               ).quantize(_D(_Q))
        return {"count": len(rows),
                "average": str(avg)}

    def subject_breakdown(self,
                          student_id
                          ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT subject, score FROM"
            " sm_evaluations WHERE"
            " student_id = ?", (student_id,))
        by = {}
        for r in rows:
            by.setdefault(str(r["subject"]),
                          []).append(
                _D(str(r["score"])))
        out = []
        for subj, scores in sorted(
                by.items()):
            avg = ((sum(scores, _D("0"))
                    / _D(str(len(scores))))
                   .quantize(_D(_Q)))
            out.append({"subject": subj,
                        "count": len(scores),
                        "average": str(avg)})
        return out
