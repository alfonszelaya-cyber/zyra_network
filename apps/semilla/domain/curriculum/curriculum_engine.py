
"""Curriculum Engine - plan de estudio (SM2).
91 materias exactas en 3 niveles."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_curriculum", (
        "CREATE TABLE IF NOT EXISTS sm_curriculum (subject_id TEXT PRIMARY KEY, level TEXT NOT NULL, grade TEXT NOT NULL, subject TEXT NOT NULL, weekly_hours INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, UNIQUE(level, grade, subject))",
    )),
)

_TEMPLATE = {
    "PARVULARIA": ["Pre-lectoescritura",
                   "Pre-numeracion",
                   "Expresion artistica",
                   "Psicomotricidad"],
    "BASICA": ["Matematica", "Lenguaje",
               "Ciencia Salud y Medio Ambiente",
               "Estudios Sociales",
               "Educacion Fisica", "Ingles",
               "Educacion Artistica"],
    "MEDIA": ["Matematica",
              "Lenguaje y Literatura",
              "Fisica", "Quimica", "Biologia",
              "Estudios Sociales y Civica",
              "Ingles", "Informatica"],
}

class CurriculumEngine:
    """Curriculo por nivel y grado."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.curriculum",
                        _MIGRATIONS).run(clock)

    def add_subject(self, *, level, grade,
                    subject,
                    weekly_hours=0) -> dict:
        sid = "SMCUR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_curriculum"
                " (subject_id, level, grade,"
                " subject, weekly_hours,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(level, grade,"
                " subject) DO UPDATE SET"
                " weekly_hours ="
                " excluded.weekly_hours",
                (sid, level, str(grade),
                 str(subject).strip(),
                 int(weekly_hours), now))
        row = self._db.query_one(
            "SELECT * FROM sm_curriculum WHERE"
            " level = ? AND grade = ? AND"
            " subject = ?",
            (level, str(grade),
             str(subject).strip()))
        return self._row(row)

    def _row(self, r) -> dict:
        return {"subject_id":
                    str(r["subject_id"]),
                "level": str(r["level"]),
                "grade": str(r["grade"]),
                "subject": str(r["subject"]),
                "weekly_hours":
                    int(r["weekly_hours"])}

    def install_template(self) -> dict:
        creadas = 0
        for level, subjects in (
                _TEMPLATE.items()):
            grades = (["Prekinder", "Kinder",
                       "Preparatoria"]
                      if level == "PARVULARIA"
                      else ([str(g) for g in
                             range(1, 10)]
                            if level == "BASICA"
                            else ["1 Bachillerato",
                                  "2 Bachillerato"]))
            for grade in grades:
                for subj in subjects:
                    self.add_subject(
                        level=level, grade=grade,
                        subject=subj)
                    creadas = creadas + 1
        return {"subjects_created": creadas}

    def subjects_of(self, level,
                    grade) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_curriculum WHERE"
            " level = ? AND grade = ?"
            " ORDER BY subject",
            (level, str(grade)))
        return [self._row(r) for r in rows]
