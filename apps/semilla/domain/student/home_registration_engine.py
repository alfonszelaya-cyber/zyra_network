
"""Home Registration Engine - matricula desde casa
(S-4, flujo del dueno + regla 78 + SE-3 COMPLETO).

FORMULARIO COMPLETO desde el celular:
- responsable (padre/madre/tutor) con ZID verificado
  por la Red
- 2 encargados de retiro autorizados (SIEMPRE, SE-3)
- contacto de emergencia
- menor con su ZID de NACIMIENTO si ya existe
  (regla 78: SEMILLA lo CONSUME — jamas crea otro)
- sin documentos NO impide iniciar (MINED lo
  permite) -> zid_status=NONE
- seleccion escuela/grado/turno -> el sistema busca
  seccion de ESE turno con CUPO; si el turno esta
  lleno -> SIN_CUPOS con nota que lista las
  alternativas con cupo (ej: "solo cupo por la
  tarde") — nunca se asigna un turno distinto sin
  avisar
- la escuela confirma -> expediente canonico en
  StudentRegistryEngine (S-1: unica fuente) + el
  CUPO se reclama UNA SOLA VEZ (via EnrollmentEngine
  — sin doble conteo) + matricula ACTIVA."""
from __future__ import annotations
from typing import Dict, List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_home_registrations", (
        "CREATE TABLE IF NOT EXISTS sm_home_registrations (request_id TEXT PRIMARY KEY, responsable_zid TEXT NOT NULL, responsable_name TEXT NOT NULL, relation TEXT NOT NULL, student_id TEXT, child_name TEXT NOT NULL, birth_date TEXT NOT NULL DEFAULT '', child_zid TEXT NOT NULL DEFAULT '', child_zid_status TEXT NOT NULL DEFAULT 'NONE', institution_id TEXT NOT NULL, level TEXT NOT NULL, grade TEXT NOT NULL, turn TEXT NOT NULL DEFAULT 'MATUTINA', classroom_id TEXT NOT NULL DEFAULT '', pickup_json TEXT NOT NULL DEFAULT '[]', emergency_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'PENDING_DOCS', note TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class HomeRegistrationEngine:
    """Matricula desde casa (formulario completo)."""

    def __init__(self, db, clock,
                 student_registry,
                 classroom_engine,
                 enrollment_engine):
        self._db = db
        self._clock = clock
        self._students = student_registry
        self._cls = classroom_engine
        self._enr = enrollment_engine
        MigrationRunner(db, "sm.homereg",
                        _MIGRATIONS).run(clock)

    def start_request(self, *, responsable_zid,
                      responsable_name, relation,
                      child_name,
                      authorized_pickup,
                      emergency_contacts,
                      birth_date="",
                      child_zid="",
                      child_zid_status="NONE",
                      institution_id, level,
                      grade, turn="MATUTINA") -> dict:
        """Pasos 1-3 del flujo: responsable + menor +
        formulario completo + seleccion de escuela.
        Valida SE-3 desde la solicitud. SOLO acepta
        seccion del turno pedido; si ese turno esta
        lleno -> SIN_CUPOS + nota con alternativas."""
        if not str(responsable_zid).strip():
            raise ValueError("responsable_zid"
                             " requerido (la Red"
                             " verifica al"
                             " responsable)")
        if relation not in ("PADRE", "MADRE",
                            "TUTOR"):
            raise ValueError("relation invalida")
        if not str(child_name).strip():
            raise ValueError(
                "child_name requerido")
        pick = list(authorized_pickup or [])
        emg = list(emergency_contacts or [])
        if len(pick) < 2:
            raise ValueError(
                "minimo 2 encargados de retiro"
                " autorizados (SE-3)")
        if len(emg) < 1:
            raise ValueError(
                "minimo 1 contacto de emergencia"
                " (SE-3)")
        if not str(institution_id).strip():
            raise ValueError(
                "institution_id requerido")
        if str(child_zid_status) not in ("NONE",
                                         "PROVISIONAL",
                                         "VERIFIED"):
            raise ValueError(
                "child_zid_status invalido")
        rid = "SMHOM-" + str(uuid.uuid4())
        now = self._clock.now()
        options = self._cls.available_sections(
            institution_id=institution_id,
            school_year="2026", level=level,
            grade=grade)
        elegida = None
        for op in options:
            if op["turn"] == turn:
                elegida = op
                break
        if elegida is not None:
            estado = "PENDING_ESCUELA"
            cid = elegida["classroom_id"]
            nota = ""
        else:
            estado = "SIN_CUPOS"
            cid = ""
            con_cupo = sorted(
                set(op["turn"]
                    for op in options))
            nota = (turn + " COMPLETADA."
                    + (" Solo cupo: "
                       + ", ".join(con_cupo)
                       if con_cupo
                       else " Sin cupos en"
                            " ningun turno"))
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_home_registrations"
                " (request_id, responsable_zid,"
                " responsable_name, relation,"
                " student_id, child_name,"
                " birth_date, child_zid,"
                " child_zid_status, institution_id,"
                " level, grade, turn, classroom_id,"
                " pickup_json, emergency_json,"
                " status, note, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, '', ?, ?, ?,"
                " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?)",
                (rid, str(responsable_zid),
                 str(responsable_name).strip(),
                 relation, str(child_name).strip(),
                 str(birth_date), str(child_zid),
                 str(child_zid_status),
                 str(institution_id), level,
                 str(grade), str(turn), cid,
                 _j.dumps(pick, default=str),
                 _j.dumps(emg, default=str),
                 estado, nota, now, now))
        return self.get_request(rid)

    def get_request(self, request_id
                    ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_home_registrations"
            " WHERE request_id = ?",
            (request_id,))
        if not row:
            return None
        return {"request_id":
                    str(row["request_id"]),
                "responsable_zid":
                    str(row["responsable_zid"]),
                "relation": str(row["relation"]),
                "student_id":
                    str(row["student_id"]),
                "child_name":
                    str(row["child_name"]),
                "child_zid":
                    str(row["child_zid"]),
                "child_zid_status":
                    str(row["child_zid_status"]),
                "institution_id":
                    str(row["institution_id"]),
                "level": str(row["level"]),
                "grade": str(row["grade"]),
                "turn": str(row["turn"]),
                "classroom_id":
                    str(row["classroom_id"]),
                "authorized_pickup": _j.loads(
                    str(row["pickup_json"])),
                "emergency_contacts": _j.loads(
                    str(row["emergency_json"])),
                "status": str(row["status"]),
                "note": str(row["note"])}

    def confirm_by_school(self, request_id,
                          director_actor) -> dict:
        """La escuela valida -> expediente canonico
        (StudentRegistryEngine) con el formulario
        COMPLETO -> matricula ACTIVA. El CUPO se
        reclama UNA SOLA VEZ dentro de enroll()
        (sin doble conteo)."""
        row = self._db.query_one(
            "SELECT * FROM sm_home_registrations"
            " WHERE request_id = ?",
            (request_id,))
        if not row:
            raise KeyError(request_id)
        estado = str(row["status"])
        if estado == "SIN_CUPOS":
            raise ValueError(
                "no se puede confirmar:"
                " SIN_CUPOS ("
                + str(row["note"]) + ")")
        if estado != "PENDING_ESCUELA":
            raise ValueError("estado: " + estado)
        est = self._students.register(
            full_name=str(row["child_name"]),
            level=str(row["level"]),
            grade=str(row["grade"]),
            institution_id=str(
                row["institution_id"]),
            tutores=[{"name": str(
                row["responsable_name"]),
                "relation": str(row["relation"]),
                "zid": str(row["responsable_zid"])}],
            authorized_pickup=_j.loads(
                str(row["pickup_json"])),
            emergency_contacts=_j.loads(
                str(row["emergency_json"])),
            zid=str(row["child_zid"]),
            zid_status=str(row["child_zid_status"]))
        enr = self._enr.enroll(
            student_id=est["student_id"],
            classroom_id=str(row["classroom_id"]),
            school_year="2026")
        self._db.execute(
            "UPDATE sm_home_registrations SET"
            " student_id = ?, status = 'ACTIVA',"
            " note = ?, updated_at = ? WHERE"
            " request_id = ?",
            (est["student_id"],
             "matriculado por "
             + str(director_actor),
             self._clock.now(), request_id))
        return {"request_id": request_id,
                "student": est,
                "enrollment": enr,
                "status": "ACTIVA"}

    def pending_requests(self,
                         institution_id
                         ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT request_id FROM"
            " sm_home_registrations WHERE"
            " institution_id = ? AND status ="
            " 'PENDING_ESCUELA' ORDER BY rowid",
            (institution_id,))
        return [self.get_request(
            str(r["request_id"]))
            for r in rows]
