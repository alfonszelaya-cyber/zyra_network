
"""Student Registry - expediente educativo (SM1).
SE-2: solo referencia ZID. SE-3: tutores + 2
encargados + emergencias obligatorios. SE-5:
official_refs source/verification elevable."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

LEVELS = ("PARVULARIA", "BASICA", "MEDIA")
ZID_STATUSES = ("NONE", "PROVISIONAL",
                "VERIFIED")
BIO_PHASES = ("NONE", "FACE", "FULL")
SOURCES = ("PARENT", "SCHOOL", "STUDENT",
           "DOCUMENT", "MINED")
VSTATUSES = ("UNVERIFIED", "SELF_REPORTED",
             "INSTITUTION_VERIFIED",
             "DOCUMENT_VERIFIED",
             "MINED_VERIFIED")

_MIGRATIONS = (
    Migration(1, "sm_students", (
        "CREATE TABLE IF NOT EXISTS sm_students (student_id TEXT PRIMARY KEY, zid TEXT NOT NULL DEFAULT '', zid_status TEXT NOT NULL DEFAULT 'NONE', full_name TEXT NOT NULL, birth_date TEXT NOT NULL DEFAULT '', birth_place TEXT NOT NULL DEFAULT '', sex TEXT NOT NULL DEFAULT '', level TEXT NOT NULL, grade TEXT NOT NULL, institution_id TEXT NOT NULL DEFAULT '', tutores_json TEXT NOT NULL DEFAULT '[]', pickup_json TEXT NOT NULL DEFAULT '[]', emergency_json TEXT NOT NULL DEFAULT '[]', official_refs_json TEXT NOT NULL DEFAULT '[]', biometric_phase TEXT NOT NULL DEFAULT 'NONE', status TEXT NOT NULL DEFAULT 'ACTIVO', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class StudentRegistryEngine:
    """Expediente educativo del estudiante."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.students",
                        _MIGRATIONS).run(clock)

    def register(self, *, full_name, level,
                 grade, birth_date="",
                 birth_place="", sex="",
                 institution_id="",
                 tutores=None,
                 authorized_pickup=None,
                 emergency_contacts=None,
                 official_refs=None,
                 zid="",
                 zid_status="NONE") -> dict:
        if level not in LEVELS:
            raise ValueError(
                "nivel invalido: " + str(level))
        if not str(full_name).strip():
            raise ValueError(
                "full_name requerido")
        tut = list(tutores or [])
        pick = list(authorized_pickup or [])
        emg = list(emergency_contacts or [])
        if len(tut) < 1:
            raise ValueError("minimo 1 tutor")
        if len(pick) < 2:
            raise ValueError(
                "minimo 2 encargados de retiro")
        if len(emg) < 1:
            raise ValueError(
                "minimo 1 contacto de"
                " emergencia")
        refs = []
        for r in (official_refs or []):
            if (r.get("source") not in SOURCES
                    or r.get("status")
                    not in VSTATUSES):
                raise ValueError(
                    "official_ref invalido")
            refs.append(dict(r))
        if zid_status not in ZID_STATUSES:
            zid_status = "NONE"
        sid = "SM-STU-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_students"
                " (student_id, zid, zid_status,"
                " full_name, birth_date,"
                " birth_place, sex, level, grade,"
                " institution_id, tutores_json,"
                " pickup_json, emergency_json,"
                " official_refs_json,"
                " biometric_phase, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?, ?, ?, ?, ?, 'NONE',"
                " 'ACTIVO', ?, ?)",
                (sid, str(zid), zid_status,
                 str(full_name).strip(),
                 str(birth_date),
                 str(birth_place), str(sex),
                 level, str(grade),
                 str(institution_id),
                 _j.dumps(tut, default=str),
                 _j.dumps(pick, default=str),
                 _j.dumps(emg, default=str),
                 _j.dumps(refs, default=str),
                 now, now))
        return self.get(sid)

    def get(self, student_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_students WHERE"
            " student_id = ?", (student_id,))
        if not row:
            return None
        return {
            "student_id":
                str(row["student_id"]),
            "zid": str(row["zid"]),
            "zid_status":
                str(row["zid_status"]),
            "full_name":
                str(row["full_name"]),
            "birth_date":
                str(row["birth_date"]),
            "birth_place":
                str(row["birth_place"]),
            "sex": str(row["sex"]),
            "level": str(row["level"]),
            "grade": str(row["grade"]),
            "institution_id":
                str(row["institution_id"]),
            "tutores": _j.loads(
                str(row["tutores_json"])),
            "authorized_pickup": _j.loads(
                str(row["pickup_json"])),
            "emergency_contacts": _j.loads(
                str(row["emergency_json"])),
            "official_refs": _j.loads(
                str(row["official_refs_json"])),
            "biometric_phase":
                str(row["biometric_phase"]),
            "status": str(row["status"])}

    def set_zid(self, student_id, zid,
                zid_status) -> dict:
        if zid_status not in ZID_STATUSES:
            raise ValueError(
                "zid_status invalido")
        self._db.execute(
            "UPDATE sm_students SET zid = ?,"
            " zid_status = ?, updated_at = ?"
            " WHERE student_id = ?",
            (str(zid), zid_status,
             self._clock.now(), student_id))
        return self.get(student_id)

    def set_biometric_phase(self, student_id,
                            phase) -> dict:
        if phase not in BIO_PHASES:
            raise ValueError("fase invalida")
        self._db.execute(
            "UPDATE sm_students SET"
            " biometric_phase = ?,"
            " updated_at = ? WHERE"
            " student_id = ?",
            (phase, self._clock.now(),
             student_id))
        return self.get(student_id)

    def add_official_ref(self, student_id, *,
                         ref_type, value, source,
                         status) -> dict:
        if source not in SOURCES:
            raise ValueError("source invalido")
        if status not in VSTATUSES:
            raise ValueError("status invalido")
        row = self._db.query_one(
            "SELECT official_refs_json FROM"
            " sm_students WHERE student_id = ?",
            (student_id,))
        if not row:
            raise KeyError(student_id)
        refs = _j.loads(
            str(row["official_refs_json"]))
        refs.append({"ref_type": str(ref_type),
                     "value": str(value),
                     "source": source,
                     "status": status})
        self._db.execute(
            "UPDATE sm_students SET"
            " official_refs_json = ?,"
            " updated_at = ? WHERE"
            " student_id = ?",
            (_j.dumps(refs, default=str),
             self._clock.now(), student_id))
        return self.get(student_id)

    def elevate_verification(self, student_id,
                             ref_type,
                             new_status) -> dict:
        if new_status not in VSTATUSES:
            raise ValueError("status invalido")
        row = self._db.query_one(
            "SELECT official_refs_json FROM"
            " sm_students WHERE student_id = ?",
            (student_id,))
        if not row:
            raise KeyError(student_id)
        refs = _j.loads(
            str(row["official_refs_json"]))
        order = VSTATUSES
        changed = False
        for r in refs:
            if r["ref_type"] == ref_type:
                if (order.index(new_status)
                        > order.index(
                            r["status"])):
                    r["status"] = new_status
                    changed = True
        if not changed:
            raise ValueError(
                "nada que elevar (o intento de"
                " degradar)")
        self._db.execute(
            "UPDATE sm_students SET"
            " official_refs_json = ?,"
            " updated_at = ? WHERE"
            " student_id = ?",
            (_j.dumps(refs, default=str),
             self._clock.now(), student_id))
        return self.get(student_id)

    def promote(self, student_id, new_level,
                new_grade) -> dict:
        if new_level not in LEVELS:
            raise ValueError("nivel invalido")
        self._db.execute(
            "UPDATE sm_students SET level = ?,"
            " grade = ?, updated_at = ? WHERE"
            " student_id = ?",
            (new_level, str(new_grade),
             self._clock.now(), student_id))
        return self.get(student_id)

    def by_institution(self,
                       institution_id,
                       level="") -> List[dict]:
        if level:
            rows = self._db.query_all(
                "SELECT student_id FROM"
                " sm_students WHERE"
                " institution_id = ? AND"
                " level = ? ORDER BY grade",
                (institution_id, level))
        else:
            rows = self._db.query_all(
                "SELECT student_id FROM"
                " sm_students WHERE"
                " institution_id = ?"
                " ORDER BY grade",
                (institution_id,))
        return [self.get(str(r["student_id"]))
                for r in rows]
