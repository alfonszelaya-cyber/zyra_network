
"""Scholarship Engine - becas completas (SM3).
Programa->aplicar->evaluar->desembolsar Decimal."""
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
PROG_STATUS = ("OPEN", "CLOSED")

_MIGRATIONS = (
    Migration(1, "sm_scholarship_programs", (
        "CREATE TABLE IF NOT EXISTS sm_scholarship_programs (program_id TEXT PRIMARY KEY, name TEXT NOT NULL, funder TEXT NOT NULL DEFAULT '', min_average TEXT NOT NULL, min_attendance_pct REAL NOT NULL, slots INTEGER NOT NULL DEFAULT 1, available INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_scholarship_apps", (
        "CREATE TABLE IF NOT EXISTS sm_scholarship_apps (application_id TEXT PRIMARY KEY, program_id TEXT NOT NULL, student_id TEXT NOT NULL, average TEXT NOT NULL DEFAULT '0.00', attendance_pct REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'APPLIED', reason TEXT NOT NULL DEFAULT '', disbursed_amount TEXT NOT NULL DEFAULT '0', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class ScholarshipEngine:
    """Becas: programa->aplicar->evaluar->desembolsar."""

    def __init__(self, db, clock,
                 evaluation_engine=None,
                 attendance_engine=None):
        self._db = db
        self._clock = clock
        self._eval = evaluation_engine
        self._att = attendance_engine
        MigrationRunner(db, "sm.scholar",
                        _MIGRATIONS).run(clock)

    def create_program(self, *, name, funder="",
                       min_average="8.00",
                       min_attendance_pct=85.0,
                       slots=1) -> dict:
        if not str(name).strip():
            raise ValueError("name requerido")
        ma = _D(str(min_average)).quantize(
            _D(_Q), rounding=_UP)
        if ma < 0 or ma > 10:
            raise ValueError(
                "min_average en escala 0-10")
        sl = int(slots)
        if sl <= 0:
            raise ValueError("slots > 0")
        pid = "SMPRG-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " sm_scholarship_programs"
                " (program_id, name, funder,"
                " min_average,"
                " min_attendance_pct, slots,"
                " available, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?,"
                " 'OPEN', ?)",
                (pid, str(name).strip(),
                 str(funder), str(ma),
                 float(min_attendance_pct),
                 sl, sl, now))
        return self.get_program(pid)

    def get_program(self, program_id
                    ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM"
            " sm_scholarship_programs WHERE"
            " program_id = ?", (program_id,))
        if not row:
            return None
        return {"program_id":
                    str(row["program_id"]),
                "name": str(row["name"]),
                "funder": str(row["funder"]),
                "min_average":
                    str(row["min_average"]),
                "min_attendance_pct":
                    float(row[
                        "min_attendance_pct"]),
                "slots": int(row["slots"]),
                "available":
                    int(row["available"]),
                "status": str(row["status"])}

    def set_call(self, program_id,
                 status) -> dict:
        if status not in PROG_STATUS:
            raise ValueError(
                "estado de convocatoria"
                " invalido")
        self._db.execute(
            "UPDATE sm_scholarship_programs"
            " SET status = ? WHERE program_id"
            " = ?", (status, program_id))
        return self.get_program(program_id)

    def _metrics(self, student_id) -> tuple:
        avg = self._eval.average_of(student_id)
        att = self._att.rate(student_id)
        return (avg["average"],
                att["present_rate_pct"])

    def apply(self, *, program_id,
              student_id) -> dict:
        prog = self.get_program(program_id)
        if not prog:
            raise KeyError(program_id)
        if prog["status"] != "OPEN":
            raise ValueError(
                "convocatoria cerrada")
        avg, att = self._metrics(student_id)
        aid = "SMAPP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            dup = cursor.execute(
                "SELECT application_id FROM"
                " sm_scholarship_apps WHERE"
                " program_id = ? AND"
                " student_id = ?",
                (program_id,
                 student_id)).fetchone()
            if dup is not None:
                raise ValueError(
                    "ya aplico a este programa")
            cursor.execute(
                "INSERT INTO"
                " sm_scholarship_apps"
                " (application_id, program_id,"
                " student_id, average,"
                " attendance_pct, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " 'APPLIED', ?, ?)",
                (aid, program_id, student_id,
                 str(avg), float(att), now,
                 now))
        return self.get_application(aid)

    def evaluate(self, application_id) -> dict:
        app = self.get_application(
            application_id)
        if not app:
            raise KeyError(application_id)
        if app["status"] != "APPLIED":
            raise ValueError(
                "solo APPLIED se evalua")
        prog = self.get_program(
            app["program_id"])
        ok = (float(app["average"])
              >= float(prog["min_average"])
              and app["attendance_pct"]
              >= prog["min_attendance_pct"])
        if not ok:
            self._db.execute(
                "UPDATE sm_scholarship_apps SET"
                " status = 'REJECTED', reason ="
                " 'no cumple criterios',"
                " updated_at = ? WHERE"
                " application_id = ?",
                (self._clock.now(),
                 application_id))
            return self.get_application(
                application_id)
        if prog["available"] <= 0:
            self._db.execute(
                "UPDATE sm_scholarship_apps SET"
                " status = 'REJECTED', reason ="
                " 'sin slots disponibles',"
                " updated_at = ? WHERE"
                " application_id = ?",
                (self._clock.now(),
                 application_id))
            return self.get_application(
                application_id)
        self._db.execute(
            "UPDATE sm_scholarship_apps SET"
            " status = 'APPROVED', reason ="
            " 'criterios cumplidos',"
            " updated_at = ? WHERE"
            " application_id = ?",
            (self._clock.now(),
             application_id))
        self._db.execute(
            "UPDATE sm_scholarship_programs SET"
            " available = available - 1 WHERE"
            " program_id = ?",
            (app["program_id"],))
        return self.get_application(
            application_id)

    def disburse(self, *, application_id,
                 amount, method="") -> dict:
        app = self.get_application(
            application_id)
        if not app:
            raise KeyError(application_id)
        if app["status"] != "APPROVED":
            raise ValueError(
                "solo APPROVED se desembolsa")
        amt = _D(str(amount)).quantize(
            _D(_Q), rounding=_UP)
        if amt <= 0:
            raise ValueError(
                "amount positivo requerido")
        self._db.execute(
            "UPDATE sm_scholarship_apps SET"
            " status = 'DISBURSED',"
            " disbursed_amount = ?, updated_at"
            " = ? WHERE application_id = ?",
            (str(amt), self._clock.now(),
             application_id))
        return self.get_application(
            application_id)

    def get_application(self, application_id
                        ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_scholarship_apps"
            " WHERE application_id = ?",
            (application_id,))
        if not row:
            return None
        return {"application_id":
                    str(row["application_id"]),
                "program_id":
                    str(row["program_id"]),
                "student_id":
                    str(row["student_id"]),
                "average": str(row["average"]),
                "attendance_pct":
                    float(row["attendance_pct"]),
                "status": str(row["status"]),
                "reason": str(row["reason"]),
                "disbursed_amount":
                    str(row["disbursed_amount"])}

    def applications_of(self, student_id
                        ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT application_id FROM"
            " sm_scholarship_apps WHERE"
            " student_id = ? ORDER BY"
            " created_at", (student_id,))
        return [self.get_application(
            str(r["application_id"]))
            for r in rows]
