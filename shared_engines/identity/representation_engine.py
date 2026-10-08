
"""Representation Engine (R-5) - 'este adulto puede
actuar POR este menor para ESTE servicio', central
en la Red (centraliza lo que SEMILLA ya hace, regla
69): alcance por servicio o '*', EXIGE vinculo
GuardianEngine activo, expiracion, revocacion,
can_act() canonico. Patron clase. Reglas 66/68/76."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_representations", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_representations (rep_id TEXT PRIMARY"
        " KEY, guardian_zid TEXT NOT NULL, minor_zid"
        " TEXT NOT NULL, service TEXT NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'activa',"
        " expires_at REAL, revoked_reason TEXT NOT"
        " NULL DEFAULT '', granted_by TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL)",
    )),
)


class RepresentationEngine:
    """Representacion legal de menores."""

    def __init__(self, db: Database, clock: Clock,
                 guardian_engine=None):
        self._db = db
        self._clock = clock
        self._guardians = guardian_engine
        MigrationRunner(db, "zid.rep",
                        _MIGRATIONS).run(clock)

    def grant(self, *, guardian_zid, minor_zid,
              service, expires_at=None,
              granted_by=""):
        g = str(guardian_zid).strip()
        m = str(minor_zid).strip()
        if not g or not m:
            raise ValueError(
                "guardian_zid y minor_zid"
                " requeridos")
        if not str(service).strip():
            raise ValueError(
                "service (alcance) requerido")
        if self._guardians is not None and \
                not self._guardians.is_guardian(
                    g, m):
            raise ValueError(
                "sin vinculo tutor activo"
                " (regla 66)")
        rid = ("ZREP-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO zid_representations"
            " (rep_id, guardian_zid, minor_zid,"
            " service, status, expires_at,"
            " granted_by, created_at)"
            " VALUES (?, ?, ?, ?, 'activa', ?, ?,"
            " ?)",
            (rid, g, m, str(service),
             (float(expires_at)
              if expires_at is not None
              else None), str(granted_by),
             self._clock.now()))
        return {"rep_id": rid,
                "service": str(service)}

    def revoke(self, rep_id, *, reason):
        row = self._db.query_one(
            "SELECT status FROM"
            " zid_representations WHERE rep_id ="
            " ?", (str(rep_id),))
        if row is None:
            raise KeyError(rep_id)
        if str(row["status"]) != "activa":
            raise ValueError("ya revocada")
        if not str(reason).strip():
            raise ValueError(
                "motivo obligatorio")
        self._db.execute(
            "UPDATE zid_representations SET"
            " status = 'revocada', revoked_reason"
            " = ? WHERE rep_id = ?",
            (str(reason), str(rep_id)))
        return {"rep_id": str(rep_id)}

    def can_act(self, guardian_zid, minor_zid,
                service):
        now = self._clock.now()
        row = self._db.query_one(
            "SELECT rep_id FROM"
            " zid_representations WHERE guardian"
            "_zid = ? AND minor_zid = ? AND status"
            " = 'activa' AND service IN (?, '*')"
            " AND (expires_at IS NULL OR expires_at"
            " > ?) LIMIT 1",
            (str(guardian_zid),
             str(minor_zid), str(service), now))
        return row is not None

    def representations_of(self, minor_zid):
        rows = self._db.query_all(
            "SELECT rep_id, guardian_zid, service,"
            " status FROM zid_representations WHERE"
            " minor_zid = ? ORDER BY rowid",
            (str(minor_zid),))
        return [{"rep_id": str(r["rep_id"]),
                 "guardian_zid": str(
                     r["guardian_zid"]),
                 "service": str(r["service"]),
                 "status": str(r["status"])}
                for r in rows]
