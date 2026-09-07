"""Verifiable credential history: bank/employer/education records.

A bank issues "client X has an active account since 2020";
an employer issues "person Y worked here from A to B"; a
school issues "degree C". These are DURABLE, REVOCABLE,
AUDITED records. Third parties query by subject and receive
the full history; integrity is backed by the audit chain.
Revocation is explicit, never a silent delete.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.errors import (
    CredentialNotFoundError,
)

EVENT_CREDENTIAL_ISSUED = "verification.credential.issued"
EVENT_CREDENTIAL_REVOKED = "verification.credential.revoked"

CREDENTIALS_MIGRATIONS = (
    Migration(
        1,
        "credentials",
        (
            "CREATE TABLE credentials ("
            " credential_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " issuer_zid TEXT NOT NULL,"
            " credential_type TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " issued_at REAL NOT NULL,"
            " valid_from REAL NOT NULL,"
            " valid_until REAL,"
            " revoked INTEGER NOT NULL DEFAULT 0,"
            " revoked_at REAL,"
            " revoked_reason TEXT,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX credentials_subject"
            " ON credentials (subject_zid)",
            "CREATE INDEX credentials_issuer"
            " ON credentials (issuer_zid)",
            "CREATE INDEX credentials_type"
            " ON credentials (credential_type)",
        ),
    ),
)


class CredentialType(Enum):
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    REFERENCE = "reference"
    FINANCIAL = "financial"
    IDENTITY_DOCUMENT = "identity_document"
    TRANSACTION_HISTORY = "transaction_history"
    KYC_VERIFIED = "kyc_verified"


@dataclass(frozen=True)
class CredentialRecord:
    credential_id: str
    subject_zid: str
    issuer_zid: str
    credential_type: CredentialType
    title: str
    detail: str
    issued_at: float
    valid_from: float
    valid_until: float | None
    revoked: bool
    revoked_at: float | None
    revoked_reason: str | None
    contract_version: int


class CredentialRegistry:
    """Durable credential history per subject, issued by others."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        MigrationRunner(
            db, "verification.credentials", CREDENTIALS_MIGRATIONS
        ).run(clock)

    def issue(
        self,
        *,
        subject_zid: str,
        issuer_zid: str,
        credential_type: CredentialType,
        title: str,
        detail: str,
        valid_from: float | None = None,
        valid_until: float | None = None,
    ) -> CredentialRecord:
        require_non_empty_str(subject_zid, "subject_zid")
        require_non_empty_str(issuer_zid, "issuer_zid")
        require_non_empty_str(title, "title")
        require_non_empty_str(detail, "detail")
        credential_id = f"CRD-{new_id()}"
        now = self._clock.now()
        valid_from_value = (
            valid_from if valid_from is not None else now
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO credentials"
                " (credential_id, subject_zid, issuer_zid,"
                "  credential_type, title, detail, issued_at,"
                "  valid_from, valid_until, revoked,"
                "  contract_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    credential_id,
                    subject_zid,
                    issuer_zid,
                    credential_type.value,
                    title,
                    detail,
                    now,
                    valid_from_value,
                    valid_until,
                    1,
                ),
            )
            event = self._catalog.build(
                EVENT_CREDENTIAL_ISSUED,
                aggregate_id=credential_id,
                payload={
                    "credential_id": credential_id,
                    "subject_zid": subject_zid,
                    "issuer_zid": issuer_zid,
                    "credential_type": credential_type.value,
                    "title": title,
                },
                clock=self._clock,
            )
            self._outbox.enqueue_in_transaction(cursor, event)
        self._audit.append(
            event_type=EVENT_CREDENTIAL_ISSUED,
            actor=issuer_zid,
            subject=credential_id,
            payload={
                "subject_zid": subject_zid,
                "credential_type": credential_type.value,
            },
        )
        record = self.get(credential_id)
        if record is None:
            raise IntegrityError(
                "credential vanished after insert"
            )
        return record

    def get(self, credential_id: str) -> CredentialRecord | None:
        row = self._db.query_one(
            "SELECT * FROM credentials WHERE credential_id = ?",
            (credential_id,),
        )
        if row is None:
            return None
        return self._record_from_row(row)

    def require(self, credential_id: str) -> CredentialRecord:
        record = self.get(credential_id)
        if record is None:
            raise CredentialNotFoundError(
                f"unknown credential: {credential_id}"
            )
        return record

    def revoke(
        self,
        credential_id: str,
        *,
        revoked_by: str,
        reason: str,
    ) -> CredentialRecord:
        require_non_empty_str(revoked_by, "revoked_by")
        require_non_empty_str(reason, "reason")
        existing = self.get(credential_id)
        if existing is None:
            raise CredentialNotFoundError(
                f"unknown credential: {credential_id}"
            )
        if existing.revoked:
            raise IntegrityError(
                f"credential {credential_id} already revoked"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE credentials SET revoked = 1,"
                " revoked_at = ?, revoked_reason = ?"
                " WHERE credential_id = ?",
                (now, reason, credential_id),
            )
            event = self._catalog.build(
                EVENT_CREDENTIAL_REVOKED,
                aggregate_id=credential_id,
                payload={
                    "credential_id": credential_id,
                    "reason": reason,
                },
                clock=self._clock,
            )
            self._outbox.enqueue_in_transaction(cursor, event)
        self._audit.append(
            event_type=EVENT_CREDENTIAL_REVOKED,
            actor=revoked_by,
            subject=credential_id,
            payload={"reason": reason},
        )
        return self.require(credential_id)

    def list_by_subject(
        self, subject_zid: str
    ) -> tuple[CredentialRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM credentials WHERE subject_zid = ?"
            " ORDER BY issued_at, credential_id",
            (subject_zid,),
        )
        return tuple(self._record_from_row(row) for row in rows)

    def list_by_issuer(
        self, issuer_zid: str
    ) -> tuple[CredentialRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM credentials WHERE issuer_zid = ?"
            " ORDER BY issued_at, credential_id",
            (issuer_zid,),
        )
        return tuple(self._record_from_row(row) for row in rows)

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> CredentialRecord:
        valid_until = row["valid_until"]
        revoked_at = row["revoked_at"]
        revoked_reason = row["revoked_reason"]
        return CredentialRecord(
            credential_id=str(row["credential_id"]),
            subject_zid=str(row["subject_zid"]),
            issuer_zid=str(row["issuer_zid"]),
            credential_type=CredentialType(
                str(row["credential_type"])
            ),
            title=str(row["title"]),
            detail=str(row["detail"]),
            issued_at=float(row["issued_at"]),
            valid_from=float(row["valid_from"]),
            valid_until=(
                None
                if valid_until is None
                else float(valid_until)
            ),
            revoked=bool(int(row["revoked"])),
            revoked_at=(
                None if revoked_at is None else float(revoked_at)
            ),
            revoked_reason=(
                None
                if revoked_reason is None
                else str(revoked_reason)
            ),
            contract_version=int(row["contract_version"]),
        )
