
"""Guardian Engine (R-2) - la relacion tutor<->menor
CANONICA de la Red, por REFERENCIA a ZIDs del
IdentityEngine existente (regla 63/69: no re-crea
ZIDs, no toca la tabla identities que es del
IdentityEngine). Roles: MADRE/PADRE/TUTOR/
REPRESENTANTE/ENCARGADO. UNIQUE(guardian,menor,rol)
activo, revocacion con motivo, re-activacion,
is_guardian() para TODAS las apps. Reglas 66/68/76."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_guardian_links", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_guardian_links (link_id TEXT PRIMARY"
        " KEY, guardian_zid TEXT NOT NULL, minor_zid"
        " TEXT NOT NULL, role TEXT NOT NULL, status"
        " TEXT NOT NULL DEFAULT 'activa', revoked"
        "_reason TEXT NOT NULL DEFAULT '', created"
        "_at REAL NOT NULL)",
        "CREATE UNIQUE INDEX IF NOT EXISTS"
        " uq_guardian_active ON zid_guardian_links"
        " (guardian_zid, minor_zid, role,"
        " CASE WHEN status = 'activa' THEN 1 ELSE"
        " NULL END)",
    )),
)
_ROLES = ("MADRE", "PADRE", "TUTOR",
          "REPRESENTANTE", "ENCARGADO")


class GuardianEngine:
    """Vinculo tutor<->menor canonico de la Red."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.guardian",
                        _MIGRATIONS).run(clock)

    def link(self, *, guardian_zid, minor_zid,
             role):
        g = str(guardian_zid).strip()
        m = str(minor_zid).strip()
        if not g or not m:
            raise ValueError(
                "guardian_zid y minor_zid"
                " requeridos")
        if g == m:
            raise ValueError(
                "guardian y minor iguales")
        r = str(role).upper()
        if r not in _ROLES:
            raise ValueError("role debe ser "
                             + "/".join(_ROLES))
        dup = self._db.query_one(
            "SELECT link_id, status FROM"
            " zid_guardian_links WHERE guardian"
            "_zid = ? AND minor_zid = ? AND role ="
            " ?", (g, m, r))
        if dup is not None and str(
                dup["status"]) == "activa":
            raise ValueError(
                "vinculo ya activo (regla 66)")
        if dup is not None:
            self._db.execute(
                "UPDATE zid_guardian_links SET"
                " status = 'activa', revoked_reason"
                " = '' WHERE link_id = ?",
                (str(dup["link_id"]),))
            return {"link_id": str(
                        dup["link_id"]),
                    "status": "activa",
                    "reactivated": True}
        lid = ("ZGL-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO zid_guardian_links"
            " (link_id, guardian_zid, minor_zid,"
            " role, status, created_at)"
            " VALUES (?, ?, ?, ?, 'activa', ?)",
            (lid, g, m, r, self._clock.now()))
        return {"link_id": lid,
                "guardian_zid": g,
                "minor_zid": m, "role": r,
                "status": "activa"}

    def revoke(self, link_id, *, reason):
        row = self._db.query_one(
            "SELECT status FROM zid_guardian_links"
            " WHERE link_id = ?", (str(link_id),))
        if row is None:
            raise KeyError(link_id)
        if str(row["status"]) != "activa":
            raise ValueError("ya revocado")
        if not str(reason).strip():
            raise ValueError(
                "motivo obligatorio")
        self._db.execute(
            "UPDATE zid_guardian_links SET status"
            " = 'revocada', revoked_reason = ?"
            " WHERE link_id = ?",
            (str(reason), str(link_id)))
        return {"link_id": str(link_id)}

    def guardians_of(self, minor_zid):
        rows = self._db.query_all(
            "SELECT link_id, guardian_zid, role"
            " FROM zid_guardian_links WHERE minor"
            "_zid = ? AND status = 'activa' ORDER"
            " BY rowid", (str(minor_zid),))
        return [{"link_id": str(r["link_id"]),
                 "guardian_zid": str(
                     r["guardian_zid"]),
                 "role": str(r["role"])}
                for r in rows]

    def minors_of(self, guardian_zid):
        rows = self._db.query_all(
            "SELECT link_id, minor_zid, role FROM"
            " zid_guardian_links WHERE guardian"
            "_zid = ? AND status = 'activa' ORDER"
            " BY rowid", (str(guardian_zid),))
        return [{"link_id": str(r["link_id"]),
                 "minor_zid": str(
                     r["minor_zid"]),
                 "role": str(r["role"])}
                for r in rows]

    def is_guardian(self, guardian_zid, minor_zid,
                    role=None):
        if role:
            row = self._db.query_one(
                "SELECT link_id FROM"
                " zid_guardian_links WHERE"
                " guardian_zid = ? AND minor_zid ="
                " ? AND role = ? AND status ="
                " 'activa'",
                (str(guardian_zid),
                 str(minor_zid),
                 str(role).upper()))
        else:
            row = self._db.query_one(
                "SELECT link_id FROM"
                " zid_guardian_links WHERE"
                " guardian_zid = ? AND minor_zid ="
                " ? AND status = 'activa'",
                (str(guardian_zid),
                 str(minor_zid)))
        return row is not None
