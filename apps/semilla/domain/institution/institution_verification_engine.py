
"""Institution Verification (SM5). Elevable sin
degradar (SE-5)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

VSTATUSES = ("PENDING", "INSTITUTION_VERIFIED",
             "MINED_VERIFIED")

_MIGRATIONS = (
    Migration(1, "sm_institution_verify", (
        "CREATE TABLE IF NOT EXISTS sm_institution_verify (verify_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, document_ref TEXT NOT NULL, document_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', verified_by TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class InstitutionVerificationEngine:
    """Verificacion documental de instituciones."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.instverify",
                        _MIGRATIONS).run(clock)

    def submit_document(self, *,
                        institution_id,
                        document_ref) -> dict:
        if not str(document_ref).strip():
            raise ValueError(
                "document_ref requerido")
        import hashlib
        h = hashlib.sha256(
            str(document_ref).encode(
                "utf-8")).hexdigest()
        vid = "SMIV-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " sm_institution_verify"
                " (verify_id, institution_id,"
                " document_ref, document_hash,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'PENDING',"
                " ?, ?)",
                (vid, institution_id,
                 str(document_ref), h, now, now))
        return self.get(vid)

    def get(self, verify_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_institution_verify"
            " WHERE verify_id = ?", (verify_id,))
        if not row:
            return None
        return {"verify_id":
                    str(row["verify_id"]),
                "institution_id":
                    str(row["institution_id"]),
                "document_ref":
                    str(row["document_ref"]),
                "document_hash":
                    str(row["document_hash"]),
                "status": str(row["status"]),
                "verified_by":
                    str(row["verified_by"])}

    def elevate(self, verify_id, new_status,
                verified_by) -> dict:
        if new_status not in VSTATUSES:
            raise ValueError("status invalido")
        row = self._db.query_one(
            "SELECT status FROM"
            " sm_institution_verify WHERE"
            " verify_id = ?", (verify_id,))
        if not row:
            raise KeyError(verify_id)
        if (VSTATUSES.index(new_status)
                <= VSTATUSES.index(
                    str(row["status"]))):
            raise ValueError(
                "nada que elevar (o intento de"
                " degradar)")
        self._db.execute(
            "UPDATE sm_institution_verify SET"
            " status = ?, verified_by = ?,"
            " updated_at = ? WHERE verify_id = ?",
            (new_status, str(verified_by),
             self._clock.now(), verify_id))
        return self.get(verify_id)

    def verifications_of(self,
                         institution_id
                         ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT verify_id FROM"
            " sm_institution_verify WHERE"
            " institution_id = ? ORDER BY rowid",
            (institution_id,))
        return [self.get(str(r["verify_id"]))
                for r in rows]
