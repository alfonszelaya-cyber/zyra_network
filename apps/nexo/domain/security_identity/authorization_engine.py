
"""Nexo Authorization Engine - RBAC con limites de
monto por empresa (NG8)."""
from __future__ import annotations
from decimal import Decimal as _D
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ROLES = ("VIEWER", "OPERATOR", "APPROVER",
         "ADMIN")
_RANK = {"VIEWER": 0, "OPERATOR": 1,
         "APPROVER": 2, "ADMIN": 3}

_MIGRATIONS = (
    Migration(1, "nexo_authz_grants", (
        "CREATE TABLE IF NOT EXISTS nexo_authz_grants (grant_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL, max_amount TEXT NOT NULL DEFAULT '0', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
)

class NexoAuthorizationEngine:
    """Permisos por empresa con tope de monto."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.authz",
                        _MIGRATIONS).run(clock)

    def grant(self, *, company_id, actor, role,
              max_amount="0") -> dict:
        if role not in ROLES:
            raise ValueError(
                "rol invalido: " + str(role))
        gid = "GRT-" + str(uuid.uuid4())
        now = self._clock.now()
        ma = _D(str(max_amount)).quantize(
            _D("0.01"))
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_authz_grants"
                " (grant_id, company_id, actor,"
                " role, max_amount, active,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, 1, ?)",
                (gid, company_id, actor, role,
                 str(ma), now))
        return self.get_grant(gid)

    def get_grant(self, grant_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_authz_grants"
            " WHERE grant_id = ?", (grant_id,))
        if not row:
            return None
        return {"grant_id": str(row["grant_id"]),
                "company_id":
                    str(row["company_id"]),
                "actor": str(row["actor"]),
                "role": str(row["role"]),
                "max_amount":
                    str(row["max_amount"]),
                "active": bool(row["active"])}

    def revoke(self, grant_id) -> dict:
        self._db.execute(
            "UPDATE nexo_authz_grants SET"
            " active = 0 WHERE grant_id = ?",
            (grant_id,))
        return self.get_grant(grant_id)

    def can(self, *, actor, company_id,
            role_needed, amount="0") -> dict:
        if role_needed not in ROLES:
            return {"allowed": False,
                    "reason": "rol desconocido"}
        row = self._db.query_one(
            "SELECT * FROM nexo_authz_grants"
            " WHERE actor = ? AND company_id = ?"
            " AND active = 1 ORDER BY created_at"
            " DESC LIMIT 1", (actor, company_id))
        if not row:
            return {"allowed": False,
                    "reason": "sin permiso"}
        grant_role = str(row["role"])
        if _RANK[grant_role] < _RANK[role_needed]:
            return {"allowed": False,
                    "reason": "rol insuficiente: "
                              + grant_role}
        ma = _D(str(row["max_amount"]))
        amt = _D(str(amount)).quantize(_D("0.01"))
        if (role_needed in ("OPERATOR",
                            "APPROVER")
                and ma > 0 and amt > ma):
            return {"allowed": False,
                    "reason": "excede limite de"
                              " monto "
                              + str(ma)}
        return {"allowed": True, "reason": "ok",
                "grant_id": str(row["grant_id"]),
                "role": grant_role}

    def grants_of(self, company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT grant_id FROM"
            " nexo_authz_grants WHERE"
            " company_id = ? ORDER BY"
            " created_at", (company_id,))
        return [self.get_grant(
            str(r["grant_id"])) for r in rows]
