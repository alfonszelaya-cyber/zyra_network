"""Signed attestations: portable, third-party verifiable claims.

An attestation is a canonical payload signed with the
Network's Ed25519 key. Anyone holding the signer public key
(embedded in the attestation itself) verifies it offline.
Issuance also publishes a versioned event through the
transactional outbox, so other engines can react.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.serialization import canonical_json_dumps
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)

ATTESTATION_FORMAT = "zyra.attestation.v1"
EVENT_ATTESTATION_ISSUED = "verification.attestation.issued"

ATTESTATION_MIGRATIONS = (
    Migration(
        1,
        "attestations",
        (
            "CREATE TABLE attestations ("
            " attestation_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " claim TEXT NOT NULL,"
            " subject_sha256 TEXT,"
            " issued_at REAL NOT NULL,"
            " signature BLOB NOT NULL,"
            " signer_public_pem BLOB NOT NULL,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX attestations_subject"
            " ON attestations (subject_zid)",
        ),
    ),
)


@dataclass(frozen=True)
class Attestation:
    attestation_id: str
    subject_zid: str
    claim: str
    subject_sha256: str | None
    issued_at: float
    signature: bytes
    signer_public_pem: bytes
    contract_version: int


def _canonical_bytes(
    attestation_id: str,
    subject_zid: str,
    claim: str,
    subject_sha256: str | None,
    issued_at: float,
) -> bytes:
    payload = {
        "format": ATTESTATION_FORMAT,
        "attestation_id": attestation_id,
        "subject_zid": subject_zid,
        "claim": claim,
        "subject_sha256": subject_sha256,
        "issued_at": f"{issued_at:.6f}",
    }
    return canonical_json_dumps(payload).encode("utf-8")


class AttestationIssuer:
    """Issues and stores signed attestations, audited + evented."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        signer: Ed25519Signer,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
    ) -> None:
        self._db = db
        self._clock = clock
        self._signer = signer
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        MigrationRunner(
            db,
            "verification.attestations",
            ATTESTATION_MIGRATIONS,
        ).run(clock)

    def issue(
        self,
        *,
        subject_zid: str,
        claim: str,
        subject_sha256: str | None = None,
    ) -> Attestation:
        require_non_empty_str(subject_zid, "subject_zid")
        require_non_empty_str(claim, "claim")
        attestation_id = f"ATT-{new_id()}"
        issued_at = self._clock.now()
        data = _canonical_bytes(
            attestation_id,
            subject_zid,
            claim,
            subject_sha256,
            issued_at,
        )
        signature = self._signer.sign(data)
        public_pem = self._signer.public_pem
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO attestations"
                " (attestation_id, subject_zid, claim,"
                "  subject_sha256, issued_at, signature,"
                "  signer_public_pem, contract_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    attestation_id,
                    subject_zid,
                    claim,
                    subject_sha256,
                    issued_at,
                    signature,
                    public_pem,
                    1,
                ),
            )
            event = self._catalog.build(
                EVENT_ATTESTATION_ISSUED,
                aggregate_id=attestation_id,
                payload={
                    "attestation_id": attestation_id,
                    "subject_zid": subject_zid,
                    "claim": claim,
                },
                clock=self._clock,
            )
            self._outbox.enqueue_in_transaction(cursor, event)
        self._audit.append(
            event_type=EVENT_ATTESTATION_ISSUED,
            actor="attestation-issuer",
            subject=attestation_id,
            payload={
                "subject_zid": subject_zid,
                "claim": claim,
            },
        )
        stored = self.get(attestation_id)
        if stored is None:
            raise IntegrityError(
                "attestation vanished after insert"
            )
        return stored

    def get(self, attestation_id: str) -> Attestation | None:
        row = self._db.query_one(
            "SELECT * FROM attestations WHERE attestation_id = ?",
            (attestation_id,),
        )
        if row is None:
            return None
        return self._attestation_from_row(row)

    def list_by_subject(
        self, subject_zid: str
    ) -> tuple[Attestation, ...]:
        rows = self._db.query_all(
            "SELECT * FROM attestations WHERE subject_zid = ?"
            " ORDER BY issued_at, attestation_id",
            (subject_zid,),
        )
        return tuple(
            self._attestation_from_row(row) for row in rows
        )

    @staticmethod
    def verify(attestation: Attestation) -> bool:
        """Third-party verification: canonical bytes + key.

        Works offline: the public key travels inside the
        attestation itself.
        """
        data = _canonical_bytes(
            attestation.attestation_id,
            attestation.subject_zid,
            attestation.claim,
            attestation.subject_sha256,
            attestation.issued_at,
        )
        verifier = Ed25519Verifier(attestation.signer_public_pem)
        return verifier.verify(data, attestation.signature)

    @staticmethod
    def _attestation_from_row(row: sqlite3.Row) -> Attestation:
        subject_sha256 = row["subject_sha256"]
        return Attestation(
            attestation_id=str(row["attestation_id"]),
            subject_zid=str(row["subject_zid"]),
            claim=str(row["claim"]),
            subject_sha256=(
                None
                if subject_sha256 is None
                else str(subject_sha256)
            ),
            issued_at=float(row["issued_at"]),
            signature=bytes(row["signature"]),
            signer_public_pem=bytes(row["signer_public_pem"]),
            contract_version=int(row["contract_version"]),
        )
