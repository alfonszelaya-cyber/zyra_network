"""Document exchange: the Network's digital notary.

The commercial heart of the verification package:

    owner seals a document (any bytes: contract,
    image, video, PDF)
          |
          v
    Network notarizes: sha256 + Ed25519 signature
    + durable integrity proof
          |
          v
    ANY third party (buyer, bank, government)
    verifies authenticity OFFLINE with only:
    document_id + content + signature +
    network public key. No database, no trust
    in the sender - just cryptography.

    plus signature requests:

    requester asks a ZID to sign a sealed doc
          |
          v
    PENDING -> SIGNED (network-notarized on
    behalf of the signer ZID) or REJECTED

Signature payloads are domain-separated:
"DOC:<id>:<sha256>" for seals and
"SIG:<req>:<doc>:<sha>:<zid>" for signatures,
so one kind can never be replayed as the other.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import (
    AuditTrail,
)
from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.integrity.engine import (
    IntegrityEngine,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)

EVENT_SEALED = "network.document.sealed"
EVENT_SIGN_REQUESTED = (
    "network.signature.requested"
)
EVENT_SIGNED = "network.document.signed"
EVENT_REJECTED = "network.document.rejected"

STATUS_PENDING = "PENDING"
STATUS_SIGNED = "SIGNED"
STATUS_REJECTED = "REJECTED"

_MIGRATIONS = (
    Migration(
        1,
        "network_document_exchange",
        (
            "CREATE TABLE sealed_documents ("
            " document_id TEXT PRIMARY KEY,"
            " owner_zid TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " sha256 TEXT NOT NULL,"
            " size_bytes INTEGER NOT NULL,"
            " network_signature BLOB"
            " NOT NULL,"
            " public_pem BLOB NOT NULL,"
            " proof_id TEXT NOT NULL,"
            " sealed_at REAL NOT NULL)",
            "CREATE TABLE"
            " signature_requests ("
            " request_id TEXT PRIMARY KEY,"
            " document_id TEXT NOT NULL,"
            " sha256 TEXT NOT NULL,"
            " signer_zid TEXT NOT NULL,"
            " requester_zid TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " resolved_at REAL,"
            " signature BLOB)",
            "CREATE INDEX sigreq_signer"
            " ON signature_requests"
            " (signer_zid, status)",
        ),
    ),
)


@dataclass(frozen=True)
class SealedDocument:
    """The owner's verifiable receipt."""

    document_id: str
    owner_zid: str
    title: str
    sha256: str
    size_bytes: int
    network_signature: bytes
    public_pem: bytes
    proof_id: str
    sealed_at: float


@dataclass(frozen=True)
class SignatureRequest:
    request_id: str
    document_id: str
    sha256: str
    signer_zid: str
    requester_zid: str
    status: str
    created_at: float
    resolved_at: float | None
    signature: bytes | None


@dataclass(frozen=True)
class DocumentVerdict:
    """Evidence-backed authenticity answer."""

    document_id: str
    hash_matches: bool
    signature_valid: bool
    authentic: bool
    evidence: dict[str, object]


def _doc_payload(
    document_id: str, sha256: str
) -> bytes:
    return (
        f"DOC:{document_id}:{sha256}"
    ).encode("utf-8")


def _sig_payload(
    *,
    request_id: str,
    document_id: str,
    sha256: str,
    signer_zid: str,
) -> bytes:
    return (
        f"SIG:{request_id}:{document_id}:"
        f"{sha256}:{signer_zid}"
    ).encode("utf-8")


class DocumentExchange:
    """Seal, sign and third-party verify."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        signer: Ed25519Signer,
        integrity: IntegrityEngine,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._signer = signer
        self._integrity = integrity
        self._audit = audit
        self._outbox = outbox
        self._public_pem = (
            signer.public_pem
        )
        MigrationRunner(
            db,
            "network.document_exchange",
            _MIGRATIONS,
        ).run(clock)

    def _require_app(
        self, app_id: str
    ) -> None:
        row = self._db.query_one(
            "SELECT 1 FROM app_registry"
            " WHERE app_id = ?",
            (app_id,),
        )
        if row is None:
            raise PermissionError(
                "app not registered:"
                f" {app_id}"
            )

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        event_type: str,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        event_id = hashlib.sha256(
            canonical_json_dumps(
                {
                    "t": event_type,
                    "a": aggregate,
                    "p": payload,
                    "ts": self._clock.now(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": event_type,
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                event_id,
                event_type,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def seal_document(
        self,
        *,
        owner_zid: str,
        title: str,
        content: bytes,
        actor_app: str,
    ) -> SealedDocument:
        """Notarize a document: hash, network
        signature, integrity proof."""
        require_non_empty_str(
            owner_zid, "owner_zid"
        )
        require_non_empty_str(
            title, "title"
        )
        self._require_app(actor_app)
        if not content:
            raise ValueError(
                "content required"
            )
        sha = hashlib.sha256(
            content
        ).hexdigest()
        document_id = f"DOC-{new_id()}"
        proof = (
            self._integrity.issue_proof(
                subject=document_id,
                data=content,
            )
        )
        signature = self._signer.sign(
            _doc_payload(
                document_id, sha
            )
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " sealed_documents"
                " (document_id, owner_zid,"
                " title, sha256,"
                " size_bytes,"
                " network_signature,"
                " public_pem, proof_id,"
                " sealed_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " ?, ?, ?, ?)",
                (
                    document_id,
                    owner_zid,
                    title,
                    sha,
                    len(content),
                    signature,
                    self._public_pem,
                    proof.proof_id,
                    now,
                ),
            )
            self._emit(
                cursor,
                event_type=EVENT_SEALED,
                aggregate=document_id,
                payload={
                    "owner": owner_zid,
                    "sha256": sha,
                    "app": actor_app,
                },
            )
        self._audit.append(
            event_type=EVENT_SEALED,
            actor=actor_app,
            subject=document_id,
            payload={
                "owner": owner_zid,
                "sha256": sha,
            },
        )
        return SealedDocument(
            document_id=document_id,
            owner_zid=owner_zid,
            title=title,
            sha256=sha,
            size_bytes=len(content),
            network_signature=(
                signature
            ),
            public_pem=self._public_pem,
            proof_id=proof.proof_id,
            sealed_at=now,
        )

    def get_sealed(
        self, *, document_id: str
    ) -> SealedDocument | None:
        row = self._db.query_one(
            "SELECT * FROM"
            " sealed_documents"
            " WHERE document_id = ?",
            (document_id,),
        )
        if row is None:
            return None
        return SealedDocument(
            document_id=str(
                row["document_id"]
            ),
            owner_zid=str(
                row["owner_zid"]
            ),
            title=str(row["title"]),
            sha256=str(row["sha256"]),
            size_bytes=int(
                row["size_bytes"]
            ),
            network_signature=bytes(
                row["network_signature"]
            ),
            public_pem=bytes(
                row["public_pem"]
            ),
            proof_id=str(
                row["proof_id"]
            ),
            sealed_at=float(
                row["sealed_at"]
            ),
        )

    def verify_document(
        self,
        *,
        document_id: str,
        content: bytes,
    ) -> DocumentVerdict:
        """Full verification against the
        sealed record."""
        sealed = self.get_sealed(
            document_id=document_id
        )
        if sealed is None:
            raise ValueError(
                "unknown document:"
                f" {document_id}"
            )
        current = hashlib.sha256(
            content
        ).hexdigest()
        hash_matches = (
            current == sealed.sha256
        )
        verifier = Ed25519Verifier(
            sealed.public_pem
        )
        signature_valid = (
            verifier.verify(
                _doc_payload(
                    document_id,
                    sealed.sha256,
                ),
                sealed.network_signature,
            )
        )
        return DocumentVerdict(
            document_id=document_id,
            hash_matches=hash_matches,
            signature_valid=(
                signature_valid
            ),
            authentic=(
                hash_matches
                and signature_valid
            ),
            evidence={
                "sealed_sha256": (
                    sealed.sha256
                ),
                "presented_sha256": (
                    current
                ),
                "proof_id": (
                    sealed.proof_id
                ),
                "owner": (
                    sealed.owner_zid
                ),
                "sealed_at": (
                    sealed.sealed_at
                ),
            },
        )

    @staticmethod
    def offline_verify(
        *,
        document_id: str,
        content: bytes,
        signature: bytes,
        public_pem: bytes,
    ) -> bool:
        """Third-party verification with NO
        database: only the receipt data."""
        sha = hashlib.sha256(
            content
        ).hexdigest()
        verifier = Ed25519Verifier(
            public_pem
        )
        return verifier.verify(
            _doc_payload(
                document_id, sha
            ),
            signature,
        )

    def request_signature(
        self,
        *,
        document_id: str,
        signer_zid: str,
        requester_zid: str,
    ) -> SignatureRequest:
        require_non_empty_str(
            signer_zid, "signer_zid"
        )
        require_non_empty_str(
            requester_zid,
            "requester_zid",
        )
        sealed = self.get_sealed(
            document_id=document_id
        )
        if sealed is None:
            raise ValueError(
                "cannot sign unknown"
                f" document:"
                f" {document_id}"
            )
        request_id = f"REQ-{new_id()}"
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " signature_requests"
                " (request_id,"
                " document_id, sha256,"
                " signer_zid,"
                " requester_zid, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " ?, ?)",
                (
                    request_id,
                    document_id,
                    sealed.sha256,
                    signer_zid,
                    requester_zid,
                    STATUS_PENDING,
                    now,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_SIGN_REQUESTED
                ),
                aggregate=request_id,
                payload={
                    "document": (
                        document_id
                    ),
                    "signer": signer_zid,
                },
            )
        self._audit.append(
            event_type=(
                EVENT_SIGN_REQUESTED
            ),
            actor=requester_zid,
            subject=request_id,
            payload={
                "document": document_id,
                "signer": signer_zid,
            },
        )
        return SignatureRequest(
            request_id=request_id,
            document_id=document_id,
            sha256=sealed.sha256,
            signer_zid=signer_zid,
            requester_zid=(
                requester_zid
            ),
            status=STATUS_PENDING,
            created_at=now,
            resolved_at=None,
            signature=None,
        )

    def _load_request(
        self,
        cursor: sqlite3.Cursor,
        request_id: str,
    ) -> sqlite3.Row:
        row: sqlite3.Row | None = cursor.execute(
            "SELECT * FROM"
            " signature_requests"
            " WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise ValueError(
                "unknown request:"
                f" {request_id}"
            )
        return row

    def sign_request(
        self,
        *,
        request_id: str,
        signer_zid: str,
    ) -> SignatureRequest:
        """The ZID signs; the Network
        notarizes on its behalf."""
        require_non_empty_str(
            signer_zid, "signer_zid"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            row = self._load_request(
                cursor, request_id
            )
            if str(row["status"]) != (
                STATUS_PENDING
            ):
                raise ValueError(
                    "request not"
                    " pending:"
                    f" {request_id}"
                )
            if str(
                row["signer_zid"]
            ) != signer_zid:
                raise PermissionError(
                    "only the requested"
                    " signer may sign"
                )
            signature = (
                self._signer.sign(
                    _sig_payload(
                        request_id=(
                            request_id
                        ),
                        document_id=str(
                            row[
                                "document_id"
                            ]
                        ),
                        sha256=str(
                            row["sha256"]
                        ),
                        signer_zid=(
                            signer_zid
                        ),
                    )
                )
            )
            cursor.execute(
                "UPDATE"
                " signature_requests"
                " SET status = ?,"
                " resolved_at = ?,"
                " signature = ?"
                " WHERE request_id = ?",
                (
                    STATUS_SIGNED,
                    now,
                    signature,
                    request_id,
                ),
            )
            self._emit(
                cursor,
                event_type=EVENT_SIGNED,
                aggregate=request_id,
                payload={
                    "signer": signer_zid,
                    "document": str(
                        row["document_id"]
                    ),
                },
            )
        self._audit.append(
            event_type=EVENT_SIGNED,
            actor=signer_zid,
            subject=request_id,
            payload={},
        )
        return self.get_request(
            request_id=request_id
        )

    def reject_request(
        self,
        *,
        request_id: str,
        signer_zid: str,
    ) -> SignatureRequest:
        require_non_empty_str(
            signer_zid, "signer_zid"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            row = self._load_request(
                cursor, request_id
            )
            if str(row["status"]) != (
                STATUS_PENDING
            ):
                raise ValueError(
                    "request not"
                    " pending:"
                    f" {request_id}"
                )
            if str(
                row["signer_zid"]
            ) != signer_zid:
                raise PermissionError(
                    "only the requested"
                    " signer may reject"
                )
            cursor.execute(
                "UPDATE"
                " signature_requests"
                " SET status = ?,"
                " resolved_at = ?"
                " WHERE request_id = ?",
                (
                    STATUS_REJECTED,
                    now,
                    request_id,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_REJECTED
                ),
                aggregate=request_id,
                payload={
                    "signer": signer_zid
                },
            )
        self._audit.append(
            event_type=EVENT_REJECTED,
            actor=signer_zid,
            subject=request_id,
            payload={},
        )
        return self.get_request(
            request_id=request_id
        )

    def get_request(
        self, *, request_id: str
    ) -> SignatureRequest:
        row = self._db.query_one(
            "SELECT * FROM"
            " signature_requests"
            " WHERE request_id = ?",
            (request_id,),
        )
        if row is None:
            raise ValueError(
                "unknown request:"
                f" {request_id}"
            )
        raw_sig = row["signature"]
        resolved = row["resolved_at"]
        return SignatureRequest(
            request_id=str(
                row["request_id"]
            ),
            document_id=str(
                row["document_id"]
            ),
            sha256=str(row["sha256"]),
            signer_zid=str(
                row["signer_zid"]
            ),
            requester_zid=str(
                row["requester_zid"]
            ),
            status=str(row["status"]),
            created_at=float(
                row["created_at"]
            ),
            resolved_at=(
                float(resolved)
                if resolved is not None
                else None
            ),
            signature=(
                bytes(raw_sig)
                if raw_sig is not None
                else None
            ),
        )

    def pending_for(
        self, *, signer_zid: str
    ) -> tuple[SignatureRequest, ...]:
        rows = self._db.query_all(
            "SELECT request_id FROM"
            " signature_requests"
            " WHERE signer_zid = ?"
            " AND status = ?"
            " ORDER BY created_at",
            (
                signer_zid,
                STATUS_PENDING,
            ),
        )
        return tuple(
            self.get_request(
                request_id=str(
                    r["request_id"]
                )
            )
            for r in rows
        )

    @staticmethod
    def verify_signature_receipt(
        *,
        request_id: str,
        document_id: str,
        sha256: str,
        signer_zid: str,
        signature: bytes,
        public_pem: bytes,
    ) -> bool:
        """Offline check of a completed
        signature, for third parties."""
        verifier = Ed25519Verifier(
            public_pem
        )
        return verifier.verify(
            _sig_payload(
                request_id=request_id,
                document_id=(
                    document_id
                ),
                sha256=sha256,
                signer_zid=signer_zid,
            ),
            signature,
        )
