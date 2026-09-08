"""Integrity engine: hashing, durable proofs and
tamper detection for content and files.

Complements (never duplicates) the audit chain:
the audit chain proves the ORDER of network
events; this engine proves the CONTENT of data.
An app stores a proof once, then can re-verify
at any time that the bytes are still exactly the
originals.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.integrity.contracts import (
    IntegrityProof,
)
from shared_engines.integrity.errors import (
    UnsupportedAlgorithmError,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

ALGORITHMS = {
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}

_MIGRATIONS = (
    Migration(
        1,
        "integrity",
        (
            "CREATE TABLE integrity_proofs ("
            " proof_id TEXT PRIMARY KEY,"
            " subject TEXT NOT NULL,"
            " algorithm TEXT NOT NULL,"
            " digest TEXT NOT NULL,"
            " size_bytes INTEGER NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX integrity_subject"
            " ON integrity_proofs"
            " (subject, created_at)",
        ),
    ),
)


class IntegrityEngine:
    """Content proofs with tamper detection."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        algorithm: str = "sha256",
    ) -> None:
        if algorithm not in ALGORITHMS:
            raise UnsupportedAlgorithmError(
                "unsupported algorithm:"
                f" {algorithm}"
            )
        self._db = db
        self._clock = clock
        self._algorithm = algorithm
        self._hasher = ALGORITHMS[
            algorithm
        ]
        MigrationRunner(
            db, "integrity", _MIGRATIONS
        ).run(clock)

    def digest_bytes(
        self, data: bytes
    ) -> str:
        return self._hasher(
            data
        ).hexdigest()

    def digest_file(
        self, path: Path
    ) -> str:
        """Streaming digest: constant memory
        regardless of file size."""
        digest = self._hasher()
        with Path(path).open("rb") as fh:
            for chunk in iter(
                lambda: fh.read(
                    512 * 1024
                ),
                b"",
            ):
                digest.update(chunk)
        return digest.hexdigest()

    def issue_proof(
        self,
        *,
        subject: str,
        data: bytes,
    ) -> IntegrityProof:
        """Store a durable proof for content."""
        require_non_empty_str(
            subject, "subject"
        )
        digest = self.digest_bytes(data)
        proof_id = f"PRF-{new_id()}"
        created_at = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " integrity_proofs"
                " (proof_id, subject,"
                " algorithm, digest,"
                " size_bytes, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    proof_id,
                    subject,
                    self._algorithm,
                    digest,
                    len(data),
                    created_at,
                ),
            )
        return IntegrityProof(
            proof_id=proof_id,
            subject=subject,
            algorithm=self._algorithm,
            digest=digest,
            size_bytes=len(data),
            created_at=created_at,
        )

    def get_proof(
        self, *, proof_id: str
    ) -> IntegrityProof:
        require_non_empty_str(
            proof_id, "proof_id"
        )
        row = self._db.query_one(
            "SELECT * FROM"
            " integrity_proofs"
            " WHERE proof_id = ?",
            (proof_id,),
        )
        if row is None:
            raise NotFoundError(
                "proof not found:"
                f" {proof_id}"
            )
        return self._proof_from_row(row)

    def proofs_for(
        self, *, subject: str
    ) -> tuple[IntegrityProof, ...]:
        require_non_empty_str(
            subject, "subject"
        )
        rows = self._db.query_all(
            "SELECT * FROM"
            " integrity_proofs"
            " WHERE subject = ?"
            " ORDER BY created_at DESC",
            (subject,),
        )
        return tuple(
            self._proof_from_row(row)
            for row in rows
        )

    def verify_proof(
        self,
        *,
        proof_id: str,
        data: bytes,
    ) -> bool:
        """Re-hash the current bytes and
        compare with the stored digest."""
        proof = self.get_proof(
            proof_id=proof_id
        )
        if (
            proof.algorithm
            not in ALGORITHMS
        ):
            raise UnsupportedAlgorithmError(
                "proof algorithm"
                " unknown:"
                f" {proof.algorithm}"
            )
        current = ALGORITHMS[
            proof.algorithm
        ](data).hexdigest()
        return current == proof.digest

    def verify_latest(
        self,
        *,
        subject: str,
        data: bytes,
    ) -> bool:
        """Verify against the most recent
        proof of a subject."""
        proofs = self.proofs_for(
            subject=subject
        )
        if not proofs:
            raise NotFoundError(
                "no proof for subject:"
                f" {subject}"
            )
        return self.verify_proof(
            proof_id=proofs[
                0
            ].proof_id,
            data=data,
        )

    @staticmethod
    def _proof_from_row(
        row: sqlite3.Row,
    ) -> IntegrityProof:
        return IntegrityProof(
            proof_id=str(
                row["proof_id"]
            ),
            subject=str(
                row["subject"]
            ),
            algorithm=str(
                row["algorithm"]
            ),
            digest=str(row["digest"]),
            size_bytes=int(
                row["size_bytes"]
            ),
            created_at=float(
                row["created_at"]
            ),
        )
