"""Federation Adapters Engine (ID-2) - ZIDs con
proveedores externos. Reglas 63/66/76."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_federation", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_federation_links (link_id TEXT PRIMARY"
        " KEY, zid TEXT NOT NULL, provider TEXT NOT"
        " NULL, external_id TEXT NOT NULL, status"
        " TEXT NOT NULL DEFAULT 'linked', created_at"
        " REAL NOT NULL, UNIQUE(provider,"
        " external_id))",
    )),
)
_PROVIDERS = ("GOOGLE", "MICROSOFT", "GOBSV",
              "CUSTOM")


class FederationAdaptersEngine:
    """Federacion de identidad (ID-2)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.fed",
                        _MIGRATIONS).run(clock)

    def link_identity(self, *, zid, provider,
                      external_id):
        if not str(zid).strip() or \
                not str(external_id).strip():
            raise ValueError(
                "zid y external_id requeridos")
        p = str(provider).upper()
        if p not in _PROVIDERS:
            raise ValueError("provider debe ser "
                             + "/".join(_PROVIDERS))
        dup = self._db.query_one(
            "SELECT link_id, zid FROM"
            " zid_federation_links WHERE provider ="
            " ? AND external_id = ?",
            (p, str(external_id)))
        if dup is not None:
            raise ValueError(
                "external_id ya vinculado a "
                + str(dup["zid"]) + " (regla 66)")
        lid = "ZFL-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_federation_links"
            " (link_id, zid, provider, external_id,"
            " status, created_at) VALUES (?, ?, ?,"
            " ?, 'linked', ?)",
            (lid, str(zid), p, str(external_id),
             self._clock.now()))
        return {"link_id": lid, "provider": p}

    def unlink_identity(self, *, zid, provider):
        rows = self._db.query_all(
            "SELECT link_id FROM zid_federation_links"
            " WHERE zid = ? AND provider = ?",
            (str(zid), str(provider).upper()))
        if not rows:
            raise LookupError(
                "sin vinculos para ese zid/"
                "provider")
        for r in rows:
            self._db.execute(
                "DELETE FROM zid_federation_links"
                " WHERE link_id = ?",
                (str(r["link_id"]),))
        return {"removed": len(rows)}

    def zid_of_external(self, *, provider,
                        external_id):
        row = self._db.query_one(
            "SELECT zid FROM zid_federation_links"
            " WHERE provider = ? AND external_id ="
            " ?", (str(provider).upper(),
                   str(external_id)))
        if row is None:
            return {"found": False}
        return {"found": True,
                "zid": str(row["zid"])}

    def links_of(self, zid):
        rows = self._db.query_all(
            "SELECT provider, external_id FROM"
            " zid_federation_links WHERE zid = ?"
            " ORDER BY rowid", (str(zid),))
        return [{"provider": str(r["provider"]),
                 "external_id": str(
                     r["external_id"])}
                for r in rows]
