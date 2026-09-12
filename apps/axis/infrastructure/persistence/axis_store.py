"""AXIS durable store v2 - additive migrations."""
from __future__ import annotations

import hashlib
import uuid

from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

ROLES = (
    "paciente",
    "medico",
    "abogado",
    "policia",
    "gobierno",
)

_MIGRATIONS = (
    Migration(
        1,
        "axis",
        (
            "CREATE TABLE axis_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE axis_medical ("
            " record_id TEXT PRIMARY KEY,"
            " patient_account TEXT NOT NULL,"
            " doctor_account TEXT NOT NULL,"
            " diagnosis TEXT NOT NULL,"
            " next_appointment TEXT,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE axis_legal_cases ("
            " case_id TEXT PRIMARY KEY,"
            " client_account TEXT NOT NULL,"
            " lawyer_account TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE axis_incidents ("
            " incident_id TEXT PRIMARY KEY,"
            " police_account TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL)",
        ),
    ),
    Migration(
        2,
        "axis_emergencias",
        (
            "CREATE TABLE axis_exams ("
            " exam_id TEXT PRIMARY KEY,"
            " patient_account TEXT NOT NULL,"
            " doctor_account TEXT NOT NULL,"
            " exam_type TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE axis_exam_results ("
            " result_id TEXT PRIMARY KEY,"
            " exam_id TEXT NOT NULL,"
            " patient_account TEXT NOT NULL,"
            " summary TEXT NOT NULL,"
            " severity TEXT NOT NULL,"
            " requires_followup INTEGER NOT NULL,"
            " followup_reason TEXT,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE axis_appointments ("
            " appointment_id TEXT PRIMARY KEY,"
            " patient_account TEXT NOT NULL,"
            " doctor_account TEXT NOT NULL,"
            " result_id TEXT,"
            " reason TEXT NOT NULL,"
            " scheduled_at TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE axis_emergencies ("
            " emergency_id TEXT PRIMARY KEY,"
            " source_app TEXT NOT NULL,"
            " subject_account TEXT,"
            " subject_zid TEXT,"
            " emergency_type TEXT NOT NULL,"
            " severity TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " resolved_at REAL)",
            "CREATE TABLE axis_dispatches ("
            " dispatch_id TEXT PRIMARY KEY,"
            " emergency_id TEXT NOT NULL,"
            " agency TEXT NOT NULL,"
            " priority TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " acknowledged_at REAL,"
            " arrived_at REAL)",
            "CREATE TABLE axis_timeline ("
            " timeline_id TEXT PRIMARY KEY,"
            " emergency_id TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " event_type TEXT NOT NULL,"
            " detail TEXT,"
            " occurred_at REAL NOT NULL)",
            "CREATE TABLE axis_evidence_chain ("
            " custody_id TEXT PRIMARY KEY,"
            " evidence_id TEXT NOT NULL,"
            " previous_hash TEXT NOT NULL,"
            " event_hash TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " action TEXT NOT NULL,"
            " document_id TEXT,"
            " occurred_at REAL NOT NULL)",
        ),
    ),
)

AGENCIES = (
    "policia",
    "bomberos",
    "ambulancia",
    "hospital",
)


class AxisStore:
    """Durable state for AXIS."""

    def __init__(self, db: Database, clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "axis", _MIGRATIONS).run(clock)

    def add_account(
        self, *, account_id: str, zid: str | None, name: str, role: str,
    ) -> dict[str, object]:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_accounts"
                " (account_id, zid, name, role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (account_id, zid, name, role, now),
            )
        return self.get_account(account_id)

    def get_account(self, account_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM axis_accounts WHERE account_id = ?",
            (account_id,),
        )
        if row is None:
            raise LookupError(f"unknown account: {account_id}")
        return {
            "account_id": str(row["account_id"]),
            "zid": (
                str(row["zid"]) if row["zid"] is not None else None
            ),
            "name": str(row["name"]),
            "role": str(row["role"]),
            "created_at": float(row["created_at"]),
        }

    def list_by_role(
        self, *, role: str,
    ) -> tuple[dict[str, object], ...]:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        rows = self._db.query_all(
            "SELECT * FROM axis_accounts WHERE role = ?"
            " ORDER BY created_at",
            (role,),
        )
        return tuple(
            {
                "account_id": str(r["account_id"]),
                "name": str(r["name"]),
            }
            for r in rows
        )

    def add_medical_record(
        self,
        *,
        record_id: str,
        patient_account: str,
        doctor_account: str,
        diagnosis: str,
        next_appointment: str | None,
        sealed_doc: str | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_medical"
                " (record_id, patient_account, doctor_account,"
                "  diagnosis, next_appointment, sealed_doc, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    patient_account,
                    doctor_account,
                    diagnosis,
                    next_appointment,
                    sealed_doc,
                    now,
                ),
            )
        return {
            "record_id": record_id,
            "diagnosis": diagnosis,
            "next_appointment": next_appointment,
        }

    def medical_records_of(
        self, *, patient_account: str,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM axis_medical"
            " WHERE patient_account = ? ORDER BY created_at",
            (patient_account,),
        )
        return tuple(
            {
                "record_id": str(r["record_id"]),
                "diagnosis": str(r["diagnosis"]),
                "next_appointment": (
                    str(r["next_appointment"])
                    if r["next_appointment"] is not None
                    else None
                ),
            }
            for r in rows
        )

    def add_legal_case(
        self,
        *,
        case_id: str,
        client_account: str,
        lawyer_account: str,
        status: str,
        detail: str,
        sealed_doc: str | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_legal_cases"
                " (case_id, client_account, lawyer_account,"
                "  status, detail, sealed_doc, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    case_id,
                    client_account,
                    lawyer_account,
                    status,
                    detail,
                    sealed_doc,
                    now,
                    now,
                ),
            )
        return self.get_case(case_id)

    def update_case_status(
        self,
        *,
        case_id: str,
        status: str,
        detail: str,
        sealed_doc: str | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE axis_legal_cases SET"
                " status = ?, detail = ?, sealed_doc = ?,"
                " updated_at = ? WHERE case_id = ?",
                (status, detail, sealed_doc, now, case_id),
            )
        return self.get_case(case_id)

    def get_case(self, case_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM axis_legal_cases WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            raise LookupError(f"unknown case: {case_id}")
        sealed = row["sealed_doc"]
        return {
            "case_id": str(row["case_id"]),
            "client_account": str(row["client_account"]),
            "lawyer_account": str(row["lawyer_account"]),
            "status": str(row["status"]),
            "detail": str(row["detail"]),
            "sealed_doc": (
                str(sealed) if sealed is not None else None
            ),
        }

    def cases_for(
        self, *, lawyer_account: str,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT case_id FROM axis_legal_cases"
            " WHERE lawyer_account = ? ORDER BY updated_at DESC",
            (lawyer_account,),
        )
        return tuple(
            self.get_case(str(r["case_id"])) for r in rows
        )

    def add_incident(
        self,
        *,
        incident_id: str,
        police_account: str,
        description: str,
        sealed_doc: str | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_incidents"
                " (incident_id, police_account, description,"
                "  sealed_doc, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (incident_id, police_account, description, sealed_doc, now),
            )
        return {
            "incident_id": incident_id,
            "description": description,
            "sealed_doc": sealed_doc,
        }

    def list_incidents(self) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM axis_incidents ORDER BY created_at DESC"
        )
        return tuple(
            {
                "incident_id": str(r["incident_id"]),
                "description": str(r["description"]),
                "sealed_doc": (
                    str(r["sealed_doc"])
                    if r["sealed_doc"] is not None
                    else None
                ),
            }
            for r in rows
        )

    def add_exam(
        self,
        *,
        exam_id: str,
        patient_account: str,
        doctor_account: str,
        exam_type: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_exams"
                " (exam_id, patient_account, doctor_account,"
                "  exam_type, status, created_at)"
                " VALUES (?, ?, ?, ?, 'ordered', ?)",
                (exam_id, patient_account, doctor_account, exam_type, now),
            )
        return {"exam_id": exam_id, "status": "ordered"}

    def add_exam_result(
        self,
        *,
        result_id: str,
        exam_id: str,
        summary: str,
        severity: str,
        requires_followup: bool,
        followup_reason: str | None,
        sealed_doc: str | None,
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT patient_account FROM axis_exams WHERE exam_id = ?",
            (exam_id,),
        )
        if row is None:
            raise LookupError(f"unknown exam: {exam_id}")
        patient = str(row["patient_account"])
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_exam_results"
                " (result_id, exam_id, patient_account, summary,"
                "  severity, requires_followup, followup_reason,"
                "  sealed_doc, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    exam_id,
                    patient,
                    summary,
                    severity,
                    1 if requires_followup else 0,
                    followup_reason,
                    sealed_doc,
                    now,
                ),
            )
            cursor.execute(
                "UPDATE axis_exams SET status = 'resulted'"
                " WHERE exam_id = ?",
                (exam_id,),
            )
        return {
            "result_id": result_id,
            "exam_id": exam_id,
            "patient_account": patient,
            "severity": severity,
            "requires_followup": requires_followup,
            "followup_reason": followup_reason,
        }

    def create_appointment(
        self,
        *,
        appointment_id: str,
        patient_account: str,
        doctor_account: str,
        result_id: str | None,
        reason: str,
        scheduled_at: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_appointments"
                " (appointment_id, patient_account, doctor_account,"
                "  result_id, reason, scheduled_at, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?)",
                (
                    appointment_id,
                    patient_account,
                    doctor_account,
                    result_id,
                    reason,
                    scheduled_at,
                    now,
                ),
            )
        return {
            "appointment_id": appointment_id,
            "patient_account": patient_account,
            "reason": reason,
            "scheduled_at": scheduled_at,
            "status": "scheduled",
        }

    def pending_reminders(self) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM axis_appointments"
            " WHERE status = 'scheduled' ORDER BY created_at"
        )
        return tuple(
            {
                "appointment_id": str(r["appointment_id"]),
                "patient_account": str(r["patient_account"]),
                "reason": str(r["reason"]),
                "scheduled_at": str(r["scheduled_at"]),
            }
            for r in rows
        )

    def create_emergency(
        self,
        *,
        emergency_id: str,
        source_app: str,
        subject_account: str | None,
        subject_zid: str | None,
        emergency_type: str,
        severity: str,
        description: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_emergencies"
                " (emergency_id, source_app, subject_account,"
                "  subject_zid, emergency_type, severity,"
                "  description, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    emergency_id,
                    source_app,
                    subject_account,
                    subject_zid,
                    emergency_type,
                    severity,
                    description,
                    now,
                ),
            )
            cursor.execute(
                "INSERT INTO axis_timeline"
                " (timeline_id, emergency_id, actor, event_type,"
                "  detail, occurred_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "TL-" + uuid.uuid4().hex[:10],
                    emergency_id,
                    source_app,
                    "emergency_created",
                    description,
                    now,
                ),
            )
        return self.get_emergency(emergency_id)

    def get_emergency(self, emergency_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM axis_emergencies WHERE emergency_id = ?",
            (emergency_id,),
        )
        if row is None:
            raise LookupError(f"unknown emergency: {emergency_id}")
        dispatches = self._db.query_all(
            "SELECT * FROM axis_dispatches WHERE emergency_id = ?"
            " ORDER BY created_at",
            (emergency_id,),
        )
        timeline = self._db.query_all(
            "SELECT * FROM axis_timeline WHERE emergency_id = ?"
            " ORDER BY occurred_at",
            (emergency_id,),
        )
        return {
            "emergency_id": str(row["emergency_id"]),
            "source_app": str(row["source_app"]),
            "subject_account": (
                str(row["subject_account"])
                if row["subject_account"] is not None
                else None
            ),
            "emergency_type": str(row["emergency_type"]),
            "severity": str(row["severity"]),
            "description": str(row["description"]),
            "status": str(row["status"]),
            "dispatches": [
                {
                    "dispatch_id": str(d["dispatch_id"]),
                    "agency": str(d["agency"]),
                    "priority": str(d["priority"]),
                    "status": str(d["status"]),
                }
                for d in dispatches
            ],
            "timeline": [
                {
                    "actor": str(t["actor"]),
                    "event_type": str(t["event_type"]),
                    "detail": (
                        str(t["detail"])
                        if t["detail"] is not None
                        else None
                    ),
                }
                for t in timeline
            ],
        }

    def dispatch_emergency(
        self, *, emergency_id: str, agency: str, priority: str,
    ) -> dict[str, object]:
        if agency not in AGENCIES:
            raise ValueError(f"unknown agency: {agency}")
        row = self._db.query_one(
            "SELECT status FROM axis_emergencies"
            " WHERE emergency_id = ?",
            (emergency_id,),
        )
        if row is None:
            raise LookupError(f"unknown emergency: {emergency_id}")
        if str(row["status"]) == "resolved":
            raise ValueError("emergency already resolved")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_dispatches"
                " (dispatch_id, emergency_id, agency, priority,"
                "  status, created_at)"
                " VALUES (?, ?, ?, ?, 'dispatched', ?)",
                (
                    "DSP-" + uuid.uuid4().hex[:10],
                    emergency_id,
                    agency,
                    priority,
                    now,
                ),
            )
            cursor.execute(
                "UPDATE axis_emergencies SET status = 'dispatched'"
                " WHERE emergency_id = ?",
                (emergency_id,),
            )
            cursor.execute(
                "INSERT INTO axis_timeline"
                " (timeline_id, emergency_id, actor, event_type,"
                "  detail, occurred_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "TL-" + uuid.uuid4().hex[:10],
                    emergency_id,
                    "axis",
                    "dispatched",
                    agency + " (" + priority + ")",
                    now,
                ),
            )
        return self.get_emergency(emergency_id)

    def resolve_emergency(self, *, emergency_id: str) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE axis_emergencies SET status = 'resolved',"
                " resolved_at = ? WHERE emergency_id = ?",
                (now, emergency_id),
            )
            cursor.execute(
                "INSERT INTO axis_timeline"
                " (timeline_id, emergency_id, actor, event_type,"
                "  detail, occurred_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "TL-" + uuid.uuid4().hex[:10],
                    emergency_id,
                    "axis",
                    "resolved",
                    None,
                    now,
                ),
            )
        return self.get_emergency(emergency_id)

    def list_open_emergencies(
        self,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT emergency_id FROM axis_emergencies"
            " WHERE status != 'resolved' ORDER BY created_at"
        )
        return tuple(
            self.get_emergency(str(r["emergency_id"]))
            for r in rows
        )

    def add_custody_event(
        self,
        *,
        evidence_id: str,
        actor_zid: str,
        action: str,
        document_id: str | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        last = self._db.query_one(
            "SELECT event_hash FROM axis_evidence_chain"
            " WHERE evidence_id = ?"
            " ORDER BY occurred_at DESC LIMIT 1",
            (evidence_id,),
        )
        if last is None:
            previous_hash = "GENESIS"
        else:
            previous_hash = str(last["event_hash"])
        metadata_hash = hashlib.sha256(
            (evidence_id + actor_zid + action).encode("utf-8")
        ).hexdigest()
        raw = (
            evidence_id
            + "|"
            + previous_hash
            + "|"
            + actor_zid
            + "|"
            + action
            + "|"
            + str(now)
            + "|"
            + metadata_hash
        )
        event_hash = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_evidence_chain"
                " (custody_id, evidence_id, previous_hash,"
                "  event_hash, actor_zid, action, document_id,"
                "  occurred_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "CUS-" + uuid.uuid4().hex[:10],
                    evidence_id,
                    previous_hash,
                    event_hash,
                    actor_zid,
                    action,
                    document_id,
                    now,
                ),
            )
        return {
            "evidence_id": evidence_id,
            "action": action,
            "actor_zid": actor_zid,
            "event_hash": event_hash,
            "previous_hash": previous_hash,
        }

    def verify_custody_chain(self, *, evidence_id: str) -> bool:
        rows = self._db.query_all(
            "SELECT * FROM axis_evidence_chain"
            " WHERE evidence_id = ? ORDER BY occurred_at",
            (evidence_id,),
        )
        previous = "GENESIS"
        for row in rows:
            metadata_hash = hashlib.sha256(
                (
                    str(row["evidence_id"])
                    + str(row["actor_zid"])
                    + str(row["action"])
                ).encode("utf-8")
            ).hexdigest()
            raw = (
                str(row["evidence_id"])
                + "|"
                + str(row["previous_hash"])
                + "|"
                + str(row["actor_zid"])
                + "|"
                + str(row["action"])
                + "|"
                + str(row["occurred_at"])
                + "|"
                + metadata_hash
            )
            expected = hashlib.sha256(
                raw.encode("utf-8")
            ).hexdigest()
            if (
                str(row["event_hash"]) != expected
                or str(row["previous_hash"]) != previous
            ):
                return False
            previous = str(row["event_hash"])
        return True

    def emergency_summary(self) -> dict[str, object]:
        open_rows = self._db.query_all(
            "SELECT emergency_id FROM axis_emergencies"
            " WHERE status != 'resolved'"
        )
        resolved = self._db.query_one(
            "SELECT COUNT(*) AS n FROM axis_emergencies"
            " WHERE status = 'resolved'"
        )
        return {
            "open_emergencies": len(open_rows),
            "resolved_emergencies": (
                int(resolved["n"]) if resolved is not None else 0
            ),
        }
