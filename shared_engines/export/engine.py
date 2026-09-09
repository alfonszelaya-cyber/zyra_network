"""Export engine: portable, signed evidence
bundles. Third parties verify offline with the
bundle + public key - no database, no trust.
Domain-separated payload
"EXPORT:<bundle_id>:<manifest_sha>"."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    EngineError,
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
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

EVENT_EXPORTED = "export.bundle.created"

_MIGRATIONS = (
    Migration(
        1,
        "export",
        (
            "CREATE TABLE"
            " export_bundles ("
            " bundle_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " entries_json BLOB NOT NULL,"
            " manifest_sha256 TEXT NOT"
            " NULL,"
            " signature BLOB NOT NULL,"
            " public_pem BLOB NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class EmptyExportError(EngineError):
    """An export needs at least one entry."""


@dataclass(frozen=True)
class ExportBundle:
    bundle_id: str
    subject_zid: str
    entries_json: bytes
    manifest_sha256: str
    signature: bytes
    public_pem: bytes
    created_at: float


def _manifest_sha(
    entries_json: bytes,
) -> str:
    return hashlib.sha256(
        entries_json
    ).hexdigest()


def _payload(
    bundle_id: str,
    manifest_sha: str,
) -> bytes:
    return (
        f"EXPORT:{bundle_id}:"
        f"{manifest_sha}"
    ).encode("utf-8")


class ExportEngine:
    """Signed portable bundles."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        signer: Ed25519Signer,
        audit: AuditTrail,
    ) -> None:
        self._db = db
        self._clock = clock
        self._signer = signer
        self._audit = audit
        self._public_pem = (
            signer.public_pem
        )
        MigrationRunner(
            db, "export", _MIGRATIONS
        ).run(clock)

    def export_bundle(
        self,
        *,
        subject_zid: str,
        entries: tuple[
            tuple[str, str, str], ...
        ],
        actor_app: str,
    ) -> ExportBundle:
        require_non_empty_str(
            subject_zid, "subject_zid"
        )
        require_non_empty_str(
            actor_app, "actor_app"
        )
        row = self._db.query_one(
            "SELECT 1 FROM app_registry"
            " WHERE app_id = ?",
            (actor_app,),
        )
        if row is None:
            raise PermissionError(
                "app not registered:"
                f" {actor_app}"
            )
        if not entries:
            raise EmptyExportError(
                "at least one entry"
                " required"
            )
        entry_docs = [
            {
                "kind": str(kind),
                "ref_id": str(ref),
                "content": str(
                    content
                ),
            }
            for kind, ref, content in (
                entries
            )
        ]
        entries_json = canonical_json_dumps(
            entry_docs
        ).encode("utf-8")
        manifest = _manifest_sha(
            entries_json
        )
        bundle_id = (
            f"EXP-{new_id()[:12]}"
        )
        signature = self._signer.sign(
            _payload(bundle_id, manifest)
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " export_bundles"
                " (bundle_id, subject_zid,"
                "  entries_json,"
                "  manifest_sha256,"
                "  signature, public_pem,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?)",
                (
                    bundle_id,
                    subject_zid,
                    entries_json,
                    manifest,
                    signature,
                    self._public_pem,
                    now,
                ),
            )
        self._audit.append(
            event_type=EVENT_EXPORTED,
            actor=actor_app,
            subject=bundle_id,
            payload={
                "subject": subject_zid,
                "entries": len(
                    entry_docs
                ),
            },
        )
        return ExportBundle(
            bundle_id=bundle_id,
            subject_zid=subject_zid,
            entries_json=entries_json,
            manifest_sha256=manifest,
            signature=signature,
            public_pem=(
                self._public_pem
            ),
            created_at=now,
        )

    def get_bundle(
        self, *, bundle_id: str
    ) -> ExportBundle:
        row = self._db.query_one(
            "SELECT * FROM"
            " export_bundles"
            " WHERE bundle_id = ?",
            (bundle_id,),
        )
        if row is None:
            raise NotFoundError(
                f"unknown bundle:"
                f" {bundle_id}"
            )
        return ExportBundle(
            bundle_id=str(
                row["bundle_id"]
            ),
            subject_zid=str(
                row["subject_zid"]
            ),
            entries_json=bytes(
                row["entries_json"]
            ),
            manifest_sha256=str(
                row["manifest_sha256"]
            ),
            signature=bytes(
                row["signature"]
            ),
            public_pem=bytes(
                row["public_pem"]
            ),
            created_at=float(
                row["created_at"]
            ),
        )

    def verify_stored(
        self, *, bundle_id: str
    ) -> bool:
        bundle = self.get_bundle(
            bundle_id=bundle_id
        )
        recomputed = _manifest_sha(
            bundle.entries_json
        )
        if (
            recomputed
            != bundle.manifest_sha256
        ):
            return False
        verifier = Ed25519Verifier(
            bundle.public_pem
        )
        return verifier.verify(
            _payload(
                bundle_id,
                bundle.manifest_sha256,
            ),
            bundle.signature,
        )

    @staticmethod
    def verify_offline(
        *,
        bundle_id: str,
        entries_json: bytes,
        signature: bytes,
        public_pem: bytes,
    ) -> bool:
        manifest = _manifest_sha(
            entries_json
        )
        verifier = Ed25519Verifier(
            public_pem
        )
        return verifier.verify(
            _payload(
                bundle_id, manifest
            ),
            signature,
        )
