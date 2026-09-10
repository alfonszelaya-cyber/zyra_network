"""AXIS durable store (5 roles)."""
from __future__ import annotations

from shared_engines.storage.database import (
    Database,
)
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
)


class AxisStore:
    """Durable state for AXIS."""

    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "axis", _MIGRATIONS
        ).run(clock)

    def add_account(
        self,
        *,
        account_id: str,
        zid: str | None,
        name: str,
        role: str,
    ) -> dict[str, object]:
        if role not in ROLES:
            raise ValueError(
                f"unknown role: {role}"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO axis_accounts"
                " (account_id, zid, name,"
                "  role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    account_id,
                    zid,
                    name,
                    role,
                    now,
                ),
            )
        return self.get_account(account_id)

    def get_account(
        self, account_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM axis_accounts"
            " WHERE account_id = ?",
            (account_id,),
        )
        if row is None:
            raise LookupError(
                "unknown account:"
                f" {account_id}"
            )
        return {
            "account_id": str(
                row["account_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"] is not None
                else None
            ),
            "name": str(row["name"]),
            "role": str(row["role"]),
            "created_at": float(
                row["created_at"]
            ),
        }

    def list_by_role(
        self, *, role: str
    ) -> tuple[dict[str, object], ...]:
        if role not in ROLES:
            raise ValueError(
                f"unknown role: {role}"
            )
        rows = self._db.query_all(
            "SELECT * FROM axis_accounts"
            " WHERE role = ?"
            " ORDER BY created_at",
            (role,),
        )
        return tuple(
            {
                "account_id": str(
                    r["account_id"]
                ),
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
                " (record_id,"
                "  patient_account,"
                "  doctor_account,"
                "  diagnosis,"
                "  next_appointment,"
                "  sealed_doc, created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                "  ?, ?)",
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
            "next_appointment": (
                next_appointment
            ),
        }

    def medical_records_of(
        self, *, patient_account: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM axis_medical"
            " WHERE patient_account = ?"
            " ORDER BY created_at",
            (patient_account,),
        )
        return tuple(
            {
                "record_id": str(
                    r["record_id"]
                ),
                "diagnosis": str(
                    r["diagnosis"]
                ),
                "next_appointment": (
                    str(
                        r[
                            "next_appointment"
                        ]
                    )
                    if r[
                        "next_appointment"
                    ]
                    is not None
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
                " (case_id, client_account,"
                "  lawyer_account, status,"
                "  detail, sealed_doc,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, ?)",
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
                " status = ?, detail = ?,"
                " sealed_doc = ?,"
                " updated_at = ?"
                " WHERE case_id = ?",
                (
                    status,
                    detail,
                    sealed_doc,
                    now,
                    case_id,
                ),
            )
        return self.get_case(case_id)

    def get_case(
        self, case_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM axis_legal_cases"
            " WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            raise LookupError(
                "unknown case:"
                f" {case_id}"
            )
        sealed = row["sealed_doc"]
        return {
            "case_id": str(row["case_id"]),
            "client_account": str(
                row["client_account"]
            ),
            "lawyer_account": str(
                row["lawyer_account"]
            ),
            "status": str(row["status"]),
            "detail": str(row["detail"]),
            "sealed_doc": (
                str(sealed)
                if sealed is not None
                else None
            ),
        }

    def cases_for(
        self, *, lawyer_account: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT case_id FROM"
            " axis_legal_cases WHERE"
            " lawyer_account = ?"
            " ORDER BY updated_at DESC",
            (lawyer_account,),
        )
        return tuple(
            self.get_case(
                str(r["case_id"])
            )
            for r in rows
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
                " (incident_id,"
                "  police_account,"
                "  description, sealed_doc,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    incident_id,
                    police_account,
                    description,
                    sealed_doc,
                    now,
                ),
            )
        return {
            "incident_id": incident_id,
            "description": description,
            "sealed_doc": sealed_doc,
        }

    def list_incidents(
        self,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM axis_incidents"
            " ORDER BY created_at DESC"
        )
        return tuple(
            {
                "incident_id": str(
                    r["incident_id"]
                ),
                "description": str(
                    r["description"]
                ),
                "sealed_doc": (
                    str(r["sealed_doc"])
                    if r["sealed_doc"]
                    is not None
                    else None
                ),
            }
            for r in rows
        )
