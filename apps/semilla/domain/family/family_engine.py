
"""Family Engine (SM4). check_consent por rowid
DESC: la mas reciente SIEMPRE manda."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

CONSENT_TYPES = ("DATA_PROCESSING", "PHOTOS",
                 "OFFSITE_ACTIVITY", "MEDICAL",
                 "INTERNET_USE")

_MIGRATIONS = (
    Migration(1, "sm_consents", (
        "CREATE TABLE IF NOT EXISTS sm_consents (consent_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, consent_type TEXT NOT NULL, status TEXT NOT NULL, granted_by TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_family_comms", (
        "CREATE TABLE IF NOT EXISTS sm_family_comms (comm_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, from_role TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
    Migration(3, "sm_family_meetings", (
        "CREATE TABLE IF NOT EXISTS sm_family_meetings (meeting_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, date TEXT NOT NULL, topic TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'SCHEDULED', notes TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class FamilyEngine:
    """Consentimientos + comunicacion familia."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.family",
                        _MIGRATIONS).run(clock)

    def grant_consent(self, *, student_id,
                      consent_type,
                      granted_by) -> dict:
        if consent_type not in CONSENT_TYPES:
            raise ValueError(
                "consent_type invalido")
        cid = "SMCNS-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_consents"
                " (consent_id, student_id,"
                " consent_type, status,"
                " granted_by, created_at)"
                " VALUES (?, ?, ?, 'GRANTED',"
                " ?, ?)",
                (cid, student_id, consent_type,
                 str(granted_by), now))
        return {"consent_id": cid,
                "consent_type": consent_type,
                "status": "GRANTED"}

    def revoke_consent(self, *, student_id,
                       consent_type,
                       revoked_by) -> dict:
        if consent_type not in CONSENT_TYPES:
            raise ValueError(
                "consent_type invalido")
        cid = "SMCNS-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_consents"
                " (consent_id, student_id,"
                " consent_type, status,"
                " granted_by, created_at)"
                " VALUES (?, ?, ?, 'REVOKED',"
                " ?, ?)",
                (cid, student_id, consent_type,
                 str(revoked_by), now))
        return {"consent_id": cid,
                "consent_type": consent_type,
                "status": "REVOKED"}

    def check_consent(self, student_id,
                      consent_type) -> bool:
        row = self._db.query_one(
            "SELECT status FROM sm_consents"
            " WHERE student_id = ? AND"
            " consent_type = ? ORDER BY"
            " rowid DESC LIMIT 1",
            (student_id, consent_type))
        if not row:
            return False
        return str(row["status"]) == "GRANTED"

    def send_communication(self, *, student_id,
                           from_role, subject,
                           body="") -> dict:
        if from_role not in ("SCHOOL",
                             "TEACHER",
                             "INSTITUTION",
                             "SYSTEM"):
            raise ValueError(
                "from_role invalido")
        if not str(subject).strip():
            raise ValueError(
                "subject requerido")
        cmid = "SMFCM-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_family_comms"
                " (comm_id, student_id,"
                " from_role, subject, body,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (cmid, student_id, from_role,
                 str(subject).strip(),
                 str(body), now))
        return {"comm_id": cmid,
                "student_id": student_id,
                "subject": str(subject).strip(),
                "status": "SENT"}

    def communications_of(self, student_id
                          ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_family_comms WHERE"
            " student_id = ? ORDER BY rowid",
            (student_id,))
        return [{"comm_id":
                     str(r["comm_id"]),
                 "from_role":
                     str(r["from_role"]),
                 "subject": str(r["subject"]),
                 "body": str(r["body"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]

    def schedule_meeting(self, *, student_id,
                         date, topic) -> dict:
        if not str(date).strip():
            raise ValueError("date requerida")
        mid = "SMFMT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_family_meetings"
                " (meeting_id, student_id, date,"
                " topic, status, created_at)"
                " VALUES (?, ?, ?, ?,"
                " 'SCHEDULED', ?)",
                (mid, student_id, str(date),
                 str(topic).strip(), now))
        return {"meeting_id": mid,
                "student_id": student_id,
                "date": str(date),
                "topic": str(topic).strip(),
                "status": "SCHEDULED"}
