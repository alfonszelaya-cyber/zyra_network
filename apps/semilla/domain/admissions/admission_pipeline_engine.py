
"""Admission Pipeline Engine (S-11) - solicitudes
de ingreso / traslados fuera de la matricula
desde casa: solicitud -> revision -> COLOCACION
con cupo REAL (compone S-7 AutoAssignmentEngine,
regla 69) -> matricula.

place(): si la solicitud no tiene student_id,
registra al alumno en el canonico con datos SE-3
completos (tutores + 2 retiro + emergencia — si
faltan, error honesto). Si el asignador responde
NO_CUPOS, la solicitud queda APROBADA con nota
(regla 66: nunca se inventa cupo)."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "admissions_table", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_admission_apps (app_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL DEFAULT"
        " '', applicant_name TEXT NOT NULL,"
        " relation TEXT NOT NULL DEFAULT '',"
        " target_institution TEXT NOT NULL,"
        " target_level TEXT NOT NULL, target_grade"
        " TEXT NOT NULL, status TEXT NOT NULL"
        " DEFAULT 'PENDIENTE', note TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
    )),
)


class AdmissionPipelineEngine:
    """Pipeline de admisiones (S-11)."""

    def __init__(self, db, clock,
                 student_registry,
                 classroom_engine,
                 enrollment_engine):
        from apps.semilla.domain.academic.auto_assignment_engine import (
            AutoAssignmentEngine,
        )
        self._db = db
        self._clock = clock
        self._students = student_registry
        self._assigner = AutoAssignmentEngine(
            db, clock,
            student_registry=student_registry,
            classroom_engine=classroom_engine,
            enrollment_engine=enrollment_engine)
        MigrationRunner(db, "sm.admissions",
                        _MIGRATIONS).run(clock)

    def create_application(self, *,
                           applicant_name,
                           target_institution,
                           target_level,
                           target_grade,
                           relation="",
                           student_id="") -> dict:
        if not str(applicant_name).strip():
            raise ValueError(
                "applicant_name requerido")
        aid = ("SMADM-"
               + uuid.uuid4().hex[:10])
        now = self._clock.now()
        self._db.execute(
            "INSERT INTO sm_admission_apps"
            " (app_id, student_id, applicant_name,"
            " relation, target_institution,"
            " target_level, target_grade, status,"
            " note, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?,"
            " 'PENDIENTE', '', ?, ?)",
            (aid, str(student_id or ""),
             str(applicant_name).strip(),
             str(relation or ""),
             str(target_institution),
             str(target_level),
             str(target_grade), now, now))
        return self.get_application(aid)

    def get_application(self, app_id) -> dict:
        row = self._db.query_one(
            "SELECT * FROM sm_admission_apps"
            " WHERE app_id = ?",
            (str(app_id),))
        if not row:
            raise KeyError(app_id)
        return {"app_id": str(row["app_id"]),
                "student_id":
                    str(row["student_id"]),
                "applicant_name":
                    str(row["applicant_name"]),
                "relation": str(row["relation"]),
                "target_institution":
                    str(row[
                        "target_institution"]),
                "target_level":
                    str(row["target_level"]),
                "target_grade":
                    str(row["target_grade"]),
                "status": str(row["status"]),
                "note": str(row["note"])}

    def review(self, app_id, *, decision,
               reviewer, note="") -> dict:
        row = self._db.query_one(
            "SELECT status FROM"
            " sm_admission_apps WHERE app_id ="
            " ?", (str(app_id),))
        if not row:
            raise KeyError(app_id)
        d = str(decision).upper()
        if d not in ("APROBADA", "RECHAZADA"):
            raise ValueError(
                "decision debe ser APROBADA o"
                " RECHAZADA")
        if str(row["status"]) != "PENDIENTE":
            raise ValueError(
                "estado: " + str(row["status"]))
        self._db.execute(
            "UPDATE sm_admission_apps SET status"
            " = ?, note = ?, updated_at = ? WHERE"
            " app_id = ?",
            (d, ("revisado por "
                 + str(reviewer)
                 + ("; " + str(note)
                    if str(note) else "")),
             self._clock.now(), str(app_id)))
        return self.get_application(app_id)

    def place(self, app_id, *, tutores,
              authorized_pickup,
              emergency_contacts,
              turn_order=None) -> dict:
        app = self.get_application(app_id)
        if app["status"] != "APROBADA":
            raise ValueError(
                "solo APROBADA se coloca;"
                " estado: "
                + app["status"])
        sid = app["student_id"]
        if not sid:
            est = self._students.register(
                full_name=app["applicant_name"],
                level=app["target_level"],
                grade=app["target_grade"],
                institution_id=app[
                    "target_institution"],
                tutores=list(tutores or []),
                authorized_pickup=list(
                    authorized_pickup or []),
                emergency_contacts=list(
                    emergency_contacts or []),
                zid="", zid_status="NONE")
            sid = est["student_id"]
            self._db.execute(
                "UPDATE sm_admission_apps SET"
                " student_id = ?, updated_at = ?"
                " WHERE app_id = ?",
                (sid, self._clock.now(),
                 str(app_id)))
        res = self._assigner.assign(
            student_id=sid,
            level=app["target_level"],
            grade=app["target_grade"],
            turn_order=turn_order,
            institution_id=app[
                "target_institution"])
        if res["status"] == "ASIGNADO":
            self._db.execute(
                "UPDATE sm_admission_apps SET"
                " status = 'MATRICULADO', note ="
                " ?, updated_at = ? WHERE app_id"
                " = ?",
                ("colocado en aula "
                 + res["classroom_id"]
                 + " turno " + res["turn"],
                 self._clock.now(),
                 str(app_id)))
        else:
            self._db.execute(
                "UPDATE sm_admission_apps SET"
                " note = ?, updated_at = ? WHERE"
                " app_id = ?",
                ("NO_CUPOS: "
                 + str(res.get("note", "")),
                 self._clock.now(),
                 str(app_id)))
        out = self.get_application(app_id)
        out["assignment"] = res
        return out
