
"""Nexo Identity Ref Engine (regla 63). SOLO
referencias: zid, proveedor, referencia del proveedor,
assurance, vigencia y hash de evidencia. JAMAS datos
personales copiados (DUI, nombre oficial, etc.)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ASSURANCE_LEVELS = ("L0", "L1", "L2", "L3",
                    "L4", "L5", "L6")

_MIGRATIONS = (
    Migration(1, "nexo_identity_refs", (
        "CREATE TABLE IF NOT EXISTS nexo_identity_refs (ref_id TEXT PRIMARY KEY, zid TEXT NOT NULL, provider TEXT NOT NULL, provider_reference TEXT NOT NULL, assurance_level TEXT NOT NULL DEFAULT 'L0', status TEXT NOT NULL DEFAULT 'ACTIVE', verified_at REAL NOT NULL, expires_at REAL, evidence_hash TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class NexoIdentityRefEngine:
    """Referencias de identidad (regla 63)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.idrefs",
                        _MIGRATIONS).run(clock)

    def register_reference(self, *, zid, provider,
                           provider_reference,
                           assurance_level="L0",
                           expires_at=None,
                           evidence_hash="") -> dict:
        if not str(zid).strip():
            raise ValueError("zid requerido")
        if not str(provider).strip():
            raise ValueError(
                "provider requerido")
        if (assurance_level
                not in ASSURANCE_LEVELS):
            assurance_level = "L0"
        rid = "IDR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_identity_refs"
                " (ref_id, zid, provider,"
                " provider_reference,"
                " assurance_level, status,"
                " verified_at, expires_at,"
                " evidence_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, 'ACTIVE',"
                " ?, ?, ?, ?)",
                (rid, zid, provider,
                 provider_reference,
                 assurance_level, now,
                 expires_at, evidence_hash,
                 now))
        return self.get_ref(rid)

    def get_ref(self, ref_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_identity_refs"
            " WHERE ref_id = ?", (ref_id,))
        if not row:
            return None
        return {"ref_id": str(row["ref_id"]),
                "zid": str(row["zid"]),
                "provider": str(row["provider"]),
                "provider_reference":
                    str(row["provider_reference"]),
                "assurance_level":
                    str(row["assurance_level"]),
                "status": str(row["status"]),
                "verified_at":
                    float(row["verified_at"]),
                "expires_at": (
                    float(row["expires_at"])
                    if row["expires_at"]
                    else None),
                "evidence_hash":
                    str(row["evidence_hash"])}

    def is_current(self, ref_id) -> bool:
        ref = self.get_ref(ref_id)
        if not ref:
            return False
        if ref["status"] != "ACTIVE":
            return False
        if (ref["expires_at"] is not None
                and ref["expires_at"]
                < self._clock.now()):
            return False
        return True

    def suspend(self, ref_id) -> dict:
        self._db.execute(
            "UPDATE nexo_identity_refs SET"
            " status = 'SUSPENDED' WHERE"
            " ref_id = ?", (ref_id,))
        return self.get_ref(ref_id)

    def refs_of(self, zid) -> List[dict]:
        rows = self._db.query_all(
            "SELECT ref_id FROM"
            " nexo_identity_refs WHERE zid = ?"
            " ORDER BY created_at", (zid,))
        return [self.get_ref(str(r["ref_id"]))
                for r in rows]
