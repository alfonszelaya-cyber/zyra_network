"""Identity Gateways Engine (ID-9) - puertos de entrada
por tipo de cliente. Reglas 63/66/76."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_gateways", (
        "CREATE TABLE IF NOT EXISTS zid_gateways ("
        " gw_id TEXT PRIMARY KEY, name TEXT NOT NULL,"
        " kind TEXT NOT NULL, owner_zid TEXT NOT NULL"
        " DEFAULT '', status TEXT NOT NULL DEFAULT"
        " 'abierta', created_at REAL NOT NULL)",
    )),
)
_KINDS = ("APP_MOVIL", "PORTAL_WEB", "API",
          "NODO_OFFLINE")


class IdentityGatewaysEngine:
    """Puertos de entrada (ID-9)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.gw",
                        _MIGRATIONS).run(clock)

    def register_gateway(self, *, name, kind,
                         owner_zid=""):
        if not str(name).strip():
            raise ValueError("name requerido")
        k = str(kind).upper()
        if k not in _KINDS:
            raise ValueError("kind debe ser "
                             + "/".join(_KINDS))
        gid = "ZGW-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_gateways (gw_id, name,"
            " kind, owner_zid, status, created_at)"
            " VALUES (?, ?, ?, ?, 'abierta', ?)",
            (gid, str(name), k, str(owner_zid),
             self._clock.now()))
        return {"gw_id": gid, "status": "abierta"}

    def close_gateway(self, gw_id):
        row = self._db.query_one(
            "SELECT status FROM zid_gateways WHERE"
            " gw_id = ?", (str(gw_id),))
        if row is None:
            raise KeyError(gw_id)
        if str(row["status"]) != "abierta":
            raise ValueError("ya cerrado")
        self._db.execute(
            "UPDATE zid_gateways SET status ="
            " 'cerrada' WHERE gw_id = ?",
            (str(gw_id),))
        return {"gw_id": str(gw_id),
                "status": "cerrada"}

    def gateways_of(self, status=""):
        if str(status).strip():
            rows = self._db.query_all(
                "SELECT gw_id, name, kind, status"
                " FROM zid_gateways WHERE status ="
                " ? ORDER BY rowid",
                (str(status).upper(),))
        else:
            rows = self._db.query_all(
                "SELECT gw_id, name, kind, status"
                " FROM zid_gateways ORDER BY rowid")
        return [{"gw_id": str(r["gw_id"]),
                 "name": str(r["name"]),
                 "kind": str(r["kind"]),
                 "status": str(r["status"])}
                for r in rows]
