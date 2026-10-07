
"""Teacher Workload Engine (S-11) - asignacion de
docentes a aulas/materias con horario simple y
control de carga honesto:
- un docente no puede estar en 2 aulas a la misma
  hora (conflicto de docente)
- un aula no puede tener 2 clases a la misma hora
  (conflicto de aula)
- tope de aulas por docente (max_classrooms,
  ValueError honesto al exceder)
- usa ClassroomEngine.set_teacher / by_teacher
  (APIs verificadas en verde).

Regla 76: consultas por rowid."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "teacher_workload", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_teacher_assignments (assignment_id"
        " TEXT PRIMARY KEY, teacher_id TEXT NOT"
        " NULL, classroom_id TEXT NOT NULL,"
        " subject TEXT NOT NULL DEFAULT '', day"
        " TEXT NOT NULL DEFAULT '', time_slot"
        " TEXT NOT NULL DEFAULT '', created_at"
        " REAL NOT NULL, UNIQUE(classroom_id,"
        " day, time_slot))",
    )),
)


class TeacherWorkloadEngine:
    """Carga docente (S-11)."""

    def __init__(self, db, clock,
                 classroom_engine,
                 max_classrooms=6):
        self._db = db
        self._clock = clock
        self._cls = classroom_engine
        self._max = int(max_classrooms)
        MigrationRunner(db, "sm.twork",
                        _MIGRATIONS).run(clock)

    def _aulas_de(self, teacher_id) -> list:
        try:
            return [str(a["classroom_id"])
                    for a in self._cls.by_teacher(
                        str(teacher_id))]
        except Exception:
            return []

    def assign(self, *, teacher_id, classroom_id,
               subject, day, time_slot) -> dict:
        self._cls.get(str(classroom_id))
        d = str(day).upper()
        ts = str(time_slot)
        row = self._db.query_one(
            "SELECT teacher_id FROM"
            " sm_teacher_assignments WHERE"
            " classroom_id = ? AND day = ? AND"
            " time_slot = ?",
            (str(classroom_id), d, ts))
        if row is not None:
            raise ValueError(
                "conflicto de AULA: ocupada el "
                + d + " " + ts)
        row2 = self._db.query_one(
            "SELECT classroom_id FROM"
            " sm_teacher_assignments WHERE"
            " teacher_id = ? AND day = ? AND"
            " time_slot = ?",
            (str(teacher_id), d, ts))
        if row2 is not None:
            raise ValueError(
                "conflicto de DOCENTE: ya tiene"
                " clase el " + d + " " + ts)
        aulas = self._aulas_de(teacher_id)
        if (str(classroom_id) not in aulas
                and len(aulas) >= self._max):
            raise ValueError(
                "tope de carga: el docente ya"
                " atiende " + str(len(aulas))
                + " aulas (max "
                + str(self._max) + ")")
        self._cls.set_teacher(
            str(classroom_id), str(teacher_id))
        aid = ("SMTW-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO sm_teacher_assignments"
            " (assignment_id, teacher_id,"
            " classroom_id, subject, day,"
            " time_slot, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (aid, str(teacher_id),
             str(classroom_id), str(subject),
             d, ts, self._clock.now()))
        return {"assignment_id": aid,
                "teacher_id": str(teacher_id),
                "classroom_id":
                    str(classroom_id),
                "subject": str(subject),
                "day": d, "time_slot": ts}

    def workload_of(self, teacher_id) -> dict:
        rows = self._db.query_all(
            "SELECT classroom_id, subject, day,"
            " time_slot FROM"
            " sm_teacher_assignments WHERE"
            " teacher_id = ? ORDER BY day,"
            " time_slot, rowid",
            (str(teacher_id),))
        items = [
            {"classroom_id":
                 str(r["classroom_id"]),
             "subject": str(r["subject"]),
             "day": str(r["day"]),
             "time_slot": str(r["time_slot"])}
            for r in rows]
        aulas = sorted(set(
            i["classroom_id"]
            for i in items))
        extra = self._aulas_de(teacher_id)
        for c in extra:
            if c not in aulas:
                aulas.append(c)
        return {"teacher_id":
                    str(teacher_id),
                "aulas": len(aulas),
                "classroom_ids": aulas,
                "slots": items,
                "max_classrooms": self._max}
