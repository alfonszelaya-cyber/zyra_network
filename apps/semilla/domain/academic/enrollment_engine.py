
"""Enrollment Engine - matricula con control de
cupo (SM1)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ENR_STATUSES = ("ACTIVA", "RETIRADA",
                "TRASLADADA", "COMPLETADA")

_MIGRATIONS = (
    Migration(1, "sm_enrollments", (
        "CREATE TABLE IF NOT EXISTS sm_enrollments (enrollment_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, classroom_id TEXT NOT NULL, institution_id TEXT NOT NULL, school_year TEXT NOT NULL, level TEXT NOT NULL, grade TEXT NOT NULL, turn TEXT NOT NULL DEFAULT 'MATUTINA', status TEXT NOT NULL DEFAULT 'ACTIVA', created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(student_id, school_year))",
    )),
)

class EnrollmentEngine:
    """Matriculas con control de cupo."""

    def __init__(self, db, clock,
                 classroom_engine=None):
        self._db = db
        self._clock = clock
        self._cls = classroom_engine
        MigrationRunner(db, "sm.enroll",
                        _MIGRATIONS).run(clock)

    def enroll(self, *, student_id, classroom_id,
               school_year) -> dict:
        room = (self._cls.get(classroom_id)
                if self._cls is not None
                else None)
        if room is None:
            raise KeyError(classroom_id)
        eid = "SMENR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            dup = cursor.execute(
                "SELECT enrollment_id FROM"
                " sm_enrollments WHERE"
                " student_id = ? AND"
                " school_year = ?",
                (student_id,
                 school_year)).fetchone()
            if dup is not None:
                raise ValueError(
                    "ya matriculado en "
                    + school_year)
        if self._cls is not None:
            self._cls.claim_seat(classroom_id,
                                 student_id)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_enrollments"
                " (enrollment_id, student_id,"
                " classroom_id, institution_id,"
                " school_year, level, grade,"
                " turn, status, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " 'ACTIVA', ?, ?)",
                (eid, student_id, classroom_id,
                 room["institution_id"],
                 school_year, room["level"],
                 room["grade"], room["turn"],
                 now, now))
        return self.get(eid)

    def get(self, enrollment_id
            ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_enrollments WHERE"
            " enrollment_id = ?",
            (enrollment_id,))
        if not row:
            return None
        return {"enrollment_id":
                    str(row["enrollment_id"]),
                "student_id":
                    str(row["student_id"]),
                "classroom_id":
                    str(row["classroom_id"]),
                "institution_id":
                    str(row["institution_id"]),
                "school_year":
                    str(row["school_year"]),
                "level": str(row["level"]),
                "grade": str(row["grade"]),
                "turn": str(row["turn"]),
                "status": str(row["status"])}

    def withdraw(self, enrollment_id,
                 status="RETIRADA") -> dict:
        if status not in ENR_STATUSES:
            raise ValueError("estado invalido")
        e = self.get(enrollment_id)
        if not e:
            raise KeyError(enrollment_id)
        if e["status"] != "ACTIVA":
            raise ValueError(
                "solo ACTIVA se cambia")
        if self._cls is not None:
            self._cls.release_seat(
                e["classroom_id"])
        self._db.execute(
            "UPDATE sm_enrollments SET"
            " status = ?, updated_at = ? WHERE"
            " enrollment_id = ?",
            (status, self._clock.now(),
             enrollment_id))
        return self.get(enrollment_id)

    def alternatives(self, *, institution_id,
                     school_year, level,
                     grade) -> List[dict]:
        if self._cls is None:
            return []
        return self._cls.available_sections(
            institution_id=institution_id,
            school_year=school_year,
            level=level, grade=grade)

    def enrollments_of(self, student_id
                       ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT enrollment_id FROM"
            " sm_enrollments WHERE"
            " student_id = ? ORDER BY"
            " created_at", (student_id,))
        return [self.get(str(r["enrollment_id"]))
                for r in rows]
