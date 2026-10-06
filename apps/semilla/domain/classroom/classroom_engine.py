
"""Classroom Engine - aulas con cupos reales (SM1)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_classrooms", (
        "CREATE TABLE IF NOT EXISTS sm_classrooms (classroom_id TEXT PRIMARY KEY, name TEXT NOT NULL, institution_id TEXT NOT NULL, school_year TEXT NOT NULL, level TEXT NOT NULL, grade TEXT NOT NULL, section TEXT NOT NULL DEFAULT 'A', turn TEXT NOT NULL DEFAULT 'MATUTINA', capacity INTEGER NOT NULL DEFAULT 30, enrolled INTEGER NOT NULL DEFAULT 0, teacher_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL)",
    )),
)

class ClassroomEngine:
    """Aulas con cupos transaccionales."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.classroom",
                        _MIGRATIONS).run(clock)

    def create(self, *, name, institution_id,
               school_year, level, grade,
               section="A",
               turn="MATUTINA", capacity=30,
               teacher_id="") -> dict:
        if int(capacity) <= 0:
            raise ValueError("capacity > 0")
        cid = "SMCLS-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_classrooms"
                " (classroom_id, name,"
                " institution_id, school_year,"
                " level, grade, section, turn,"
                " capacity, enrolled, teacher_id,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, 0, ?, 'OPEN', ?)",
                (cid, str(name).strip(),
                 institution_id, school_year,
                 level, str(grade),
                 str(section), str(turn),
                 int(capacity),
                 str(teacher_id), now))
        return self.get(cid)

    def _row(self, r) -> dict:
        cap = int(r["capacity"])
        enr = int(r["enrolled"])
        return {"classroom_id":
                    str(r["classroom_id"]),
                "name": str(r["name"]),
                "institution_id":
                    str(r["institution_id"]),
                "school_year":
                    str(r["school_year"]),
                "level": str(r["level"]),
                "grade": str(r["grade"]),
                "section": str(r["section"]),
                "turn": str(r["turn"]),
                "capacity": cap,
                "enrolled": enr,
                "cupos": cap - enr,
                "teacher_id":
                    str(r["teacher_id"]),
                "status": str(r["status"])}

    def get(self, classroom_id
            ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_classrooms WHERE"
            " classroom_id = ?",
            (classroom_id,))
        return self._row(row) if row else None

    def claim_seat(self, classroom_id,
                   student_id) -> dict:
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT * FROM sm_classrooms"
                " WHERE classroom_id = ?",
                (classroom_id,)).fetchone()
            if row is None:
                raise KeyError(classroom_id)
            cap = int(row["capacity"])
            enr = int(row["enrolled"])
            if (str(row["status"])
                    == "COMPLETADA"
                    or enr >= cap):
                raise ValueError(
                    "MATRICULA COMPLETADA: "
                    + str(row["grade"])
                    + " seccion "
                    + str(row["section"])
                    + " turno "
                    + str(row["turn"])
                    + " sin cupos")
            cursor.execute(
                "UPDATE sm_classrooms SET"
                " enrolled = enrolled + 1 WHERE"
                " classroom_id = ?",
                (classroom_id,))
            if enr + 1 >= cap:
                cursor.execute(
                    "UPDATE sm_classrooms SET"
                    " status = 'COMPLETADA'"
                    " WHERE classroom_id = ?",
                    (classroom_id,))
        return self.get(classroom_id)

    def release_seat(self, classroom_id) -> dict:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE sm_classrooms SET"
                " enrolled = CASE WHEN enrolled"
                " > 0 THEN enrolled - 1 ELSE 0"
                " END, status = 'OPEN' WHERE"
                " classroom_id = ?",
                (classroom_id,))
        return self.get(classroom_id)

    def available_sections(self, *,
                           institution_id,
                           school_year, level,
                           grade) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_classrooms WHERE"
            " institution_id = ? AND"
            " school_year = ? AND level = ? AND"
            " grade = ? AND status = 'OPEN'"
            " ORDER BY turn, section",
            (institution_id, school_year,
             level, str(grade)))
        out = []
        for r in rows:
            d = self._row(r)
            if d["cupos"] > 0:
                out.append(d)
        return out

    def set_teacher(self, classroom_id,
                    teacher_id) -> dict:
        self._db.execute(
            "UPDATE sm_classrooms SET"
            " teacher_id = ? WHERE"
            " classroom_id = ?",
            (str(teacher_id), classroom_id))
        return self.get(classroom_id)

    def by_teacher(self, teacher_id
                   ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT classroom_id FROM"
            " sm_classrooms WHERE"
            " teacher_id = ? ORDER BY"
            " created_at", (teacher_id,))
        return [self.get(
            str(r["classroom_id"]))
            for r in rows]
