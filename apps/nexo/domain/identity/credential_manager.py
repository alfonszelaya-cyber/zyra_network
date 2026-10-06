
"""Nexo Credential Manager - credenciales por
referencia (regla 63)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_credential_refs", (
        "CREATE TABLE IF NOT EXISTS nexo_credential_refs (cred_id TEXT PRIMARY KEY, zid TEXT NOT NULL, credential_type TEXT NOT NULL, issuer TEXT NOT NULL, reference TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', issued_at REAL NOT NULL, expires_at REAL, revoked_reason TEXT NOT NULL DEFAULT '')",
    )),
)

class NexoCredentialManager:
    """Credenciales por referencia (regla 63)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.creds",
                        _MIGRATIONS).run(clock)

    def issue(self, *, zid, credential_type,
              issuer, reference="",
              expires_at=None) -> dict:
        if not str(zid).strip():
            raise ValueError("zid requerido")
        if not str(issuer).strip():
            raise ValueError(
                "issuer requerido")
        cid = "CRD-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_credential_refs"
                " (cred_id, zid, credential_type,"
                " issuer, reference, status,"
                " issued_at, expires_at,"
                " revoked_reason)"
                " VALUES (?, ?, ?, ?, ?, 'ACTIVE',"
                " ?, ?, '')",
                (cid, zid, credential_type,
                 issuer, reference, now,
                 expires_at))
        return self.get_cred(cid)

    def get_cred(self, cred_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_credential_refs"
            " WHERE cred_id = ?", (cred_id,))
        if not row:
            return None
        return {"cred_id": str(row["cred_id"]),
                "zid": str(row["zid"]),
                "credential_type":
                    str(row["credential_type"]),
                "issuer": str(row["issuer"]),
                "reference":
                    str(row["reference"]),
                "status": str(row["status"]),
                "issued_at":
                    float(row["issued_at"]),
                "expires_at": (
                    float(row["expires_at"])
                    if row["expires_at"]
                    else None),
                "revoked_reason":
                    str(row["revoked_reason"])}

    def verify(self, cred_id) -> dict:
        c = self.get_cred(cred_id)
        if not c:
            return {"valid": False,
                    "reason": "no existe"}
        if c["status"] == "REVOKED":
            return {"valid": False,
                    "reason": "revocada: "
                              + c["revoked_reason"]}
        if (c["expires_at"] is not None
                and c["expires_at"]
                < self._clock.now()):
            return {"valid": False,
                    "reason": "expirada"}
        return {"valid": True,
                "reason": "ok",
                "credential_type":
                    c["credential_type"]}

    def revoke(self, *, cred_id,
               reason="") -> dict:
        self._db.execute(
            "UPDATE nexo_credential_refs SET"
            " status = 'REVOKED',"
            " revoked_reason = ? WHERE"
            " cred_id = ?", (reason, cred_id))
        return self.get_cred(cred_id)

    def creds_of(self, zid) -> List[dict]:
        rows = self._db.query_all(
            "SELECT cred_id FROM"
            " nexo_credential_refs WHERE"
            " zid = ? ORDER BY issued_at",
            (zid,))
        return [self.get_cred(
            str(r["cred_id"])) for r in rows]
