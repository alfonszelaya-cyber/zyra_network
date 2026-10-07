
"""Learning Path Engine (S-13) - rutas de estudio
personalizadas por materia, alimentadas por la
IA tutora integrada (S-8) y los promedios reales
(S-9): 3 pasos por materia con dificultad base
= objetivo ACTIVO de esa materia (si existe),
si no, derivada del promedio; sin notas ->
ruta GENERAL nivel 1 (razon honesta, regla 66).

Regla 61: porcentaje Decimal 2d. Regla 76:
ORDER BY subject, step_no, rowid."""
from __future__ import annotations
import uuid
from decimal import Decimal
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "learning_own", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_learning_paths (path_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL, subject"
        " TEXT NOT NULL, step_no INTEGER NOT NULL,"
        " difficulty INTEGER NOT NULL DEFAULT 1,"
        " status TEXT NOT NULL DEFAULT 'ACTIVO',"
        " created_at REAL NOT NULL, updated_at"
        " REAL NOT NULL, UNIQUE(student_id,"
        " subject, step_no))",
    )),
)


def _base_from_average(avg):
    if avg is None:
        return 1
    d = Decimal(str(avg))
    if d < Decimal("5.00"):
        return 1
    if d < Decimal("7.00"):
        return 2
    if d < Decimal("9.00"):
        return 3
    return 4


class LearningPathEngine:
    """Rutas personalizadas (S-13)."""

    def __init__(self, db, clock,
                 tutor_link=None):
        self._db = db
        self._clock = clock
        self._tutor = tutor_link
        MigrationRunner(db, "sm.learning",
                        _MIGRATIONS).run(clock)

    def _base_difficulty(self, student_id,
                         subject) -> int:
        if self._tutor is not None:
            for o in self._tutor.objectives_of(
                    student_id):
                if (o["subject"] == subject
                        and o["status"]
                        == "ACTIVO"):
                    return int(
                        o["difficulty"])
        row = self._db.query_one(
            "SELECT AVG(CAST(score AS REAL)) AS"
            " a FROM sm_evaluations WHERE"
            " student_id = ? AND subject = ?",
            (str(student_id), str(subject)))
        if row is not None and \
                row["a"] is not None:
            return _base_from_average(
                row["a"])
        return 1

    def build_path(self, student_id) -> dict:
        rows = self._db.query_all(
            "SELECT DISTINCT subject FROM"
            " sm_evaluations WHERE student_id ="
            " ?", (str(student_id),))
        subjects = sorted(set(
            str(r["subject"]) for r in rows))
        note = ""
        if not subjects:
            subjects = ["GENERAL"]
            note = ("sin notas: ruta GENERAL"
                    " nivel 1")
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM sm_learning_paths"
                " WHERE student_id = ?",
                (str(student_id),))
            built = {}
            for subj in subjects:
                base = self._base_difficulty(
                    student_id, subj)
                for step in (1, 2, 3):
                    diff = min(5, base
                               + (step - 1))
                    cur.execute(
                        "INSERT INTO"
                        " sm_learning_paths"
                        " (path_id, student_id,"
                        " subject, step_no,"
                        " difficulty, status,"
                        " created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?,"
                        " 'ACTIVO', ?, ?)",
                        ("SMPTH-"
                         + uuid.uuid4()
                         .hex[:10],
                         str(student_id),
                         subj, step, diff,
                         self._clock.now(),
                         self._clock.now()))
                built[subj] = {
                    "base": base,
                    "steps": [
                        min(5, base
                            + (s - 1))
                        for s in (1, 2, 3)]}
        return {"student_id":
                    str(student_id),
                "by_subject": built,
                "total_steps":
                    3 * len(subjects),
                "note": note}

    def complete_step(self, path_id) -> dict:
        row = self._db.query_one(
            "SELECT path_id FROM"
            " sm_learning_paths WHERE"
            " path_id = ?", (str(path_id),))
        if not row:
            raise KeyError(path_id)
        self._db.execute(
            "UPDATE sm_learning_paths SET"
            " status = 'COMPLETADO',"
            " updated_at = ? WHERE path_id = ?",
            (self._clock.now(),
             str(path_id)))
        return {"path_id": str(path_id),
                "status": "COMPLETADO"}

    def progress(self, student_id) -> dict:
        tot = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sm_learning_paths WHERE"
            " student_id = ?",
            (str(student_id),))
        done = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sm_learning_paths WHERE"
            " student_id = ? AND status ="
            " 'COMPLETADO'",
            (str(student_id),))
        total = int(tot["n"]) if tot else 0
        comp = int(done["n"]) if done else 0
        if total > 0:
            pct = str(
                ((Decimal(comp)
                  / Decimal(total))
                 * Decimal(100))
                .quantize(Decimal("0.01")))
        else:
            pct = "0.00"
        nxt = self._db.query_one(
            "SELECT subject, step_no, difficulty"
            " FROM sm_learning_paths WHERE"
            " student_id = ? AND status ="
            " 'ACTIVO' ORDER BY subject,"
            " step_no, rowid LIMIT 1",
            (str(student_id),))
        next_step = None
        if nxt is not None:
            next_step = {
                "subject": str(
                    nxt["subject"]),
                "step_no": int(
                    nxt["step_no"]),
                "difficulty": int(
                    nxt["difficulty"])}
        return {"student_id":
                    str(student_id),
                "total": total,
                "completed": comp,
                "pct": pct,
                "next_step": next_step}
