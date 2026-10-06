
"""Nexo Identity Validation - validaciones (NG8).
ID unico por fila."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

KNOWN_PROVIDERS = ("RNPN", "LOGIN_SV",
                   "PASSPORT", "FOREIGN_ID",
                   "NEXO")

_MIGRATIONS = (
    Migration(1, "nexo_identity_validations", (
        "CREATE TABLE IF NOT EXISTS nexo_identity_validations (validation_id TEXT PRIMARY KEY, subject TEXT NOT NULL, validation_type TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', validated_at REAL NOT NULL)",
    )),
)

class NexoIdentityValidation:
    """Validaciones de referencias persistidas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.idval",
                        _MIGRATIONS).run(clock)

    def validate_reference(self, *, zid, provider,
                           expires_at=None) -> dict:
        checks = []
        checks.append(("ZID_REQUIRED",
                       bool(str(zid).strip()),
                       "zid="
                       + ("ok" if str(zid).strip()
                          else "vacio")))
        checks.append(("PROVIDER_KNOWN",
                       provider in
                       KNOWN_PROVIDERS,
                       "provider=" + str(provider)))
        exp_ok = True
        if expires_at is not None:
            exp_ok = (float(expires_at)
                      > self._clock.now())
        checks.append(("EXPIRY_FUTURE", exp_ok,
                       "expires_at="
                       + str(expires_at)))
        now = self._clock.now()
        ids = []
        with self._db.transaction() as cursor:
            for vtype, ok, detail in checks:
                vid = "IDV-" + str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO"
                    " nexo_identity_validations"
                    " (validation_id, subject,"
                    " validation_type, passed,"
                    " detail, validated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (vid, "identity_ref", vtype,
                     1 if ok else 0, detail, now))
                ids.append(vid)
        failed = [c for c in checks if not c[1]]
        return {"row_ids": ids,
                "valid": len(failed) == 0,
                "checks": [{"check": c,
                            "passed": okk,
                            "detail": d}
                           for c, okk, d
                           in checks]}
