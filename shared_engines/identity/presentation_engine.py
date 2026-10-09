"""Presentation Engine (ID-7) - presentaciones
verificables con selective disclosure + sello HMAC.
Verificacion en ORDEN correcto:
1) comparar datos recibidos vs ALMACENADOS
2) verificar sello HMAC (anti-alteracion post-emision)
Reglas 63/66/76."""
from __future__ import annotations
import hashlib, hmac, json, os, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_presentations", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_presentations (pres_id TEXT PRIMARY"
        " KEY, zid TEXT NOT NULL, fields_json TEXT"
        " NOT NULL, nonce TEXT NOT NULL, seal TEXT"
        " NOT NULL, verified INTEGER NOT NULL"
        " DEFAULT 0, created_at REAL NOT NULL)",
    )),
)


class PresentationEngine:
    """Presentaciones verificables (ID-7)."""

    def __init__(self, db: Database, clock: Clock,
                 master_key=None):
        self._db = db
        self._clock = clock
        self._master = (str(master_key)
                        if master_key
                        else os.environ.get(
                            "ZYRA_ROOT_KEY", "")
                        or "zyra-default-dev-key")
        MigrationRunner(db, "zid.present",
                        _MIGRATIONS).run(clock)

    def _seal(self, zid, fields, nonce):
        payload = json.dumps(
            {"zid": str(zid), "fields": fields,
             "nonce": nonce}, sort_keys=True)
        return hmac.new(
            self._master.encode(),
            payload.encode(),
            hashlib.sha256).hexdigest()

    def present(self, *, zid, fields, verifier=""):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        if not fields or not isinstance(fields,
                                        dict):
            raise ValueError(
                "fields debe ser objeto no vacio")
        nonce = os.urandom(16).hex()
        seal = self._seal(zid, fields, nonce)
        pid = "ZPR-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_presentations (pres_id,"
            " zid, fields_json, nonce, seal, verified,"
            " created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (pid, str(zid),
             json.dumps(fields, sort_keys=True),
             nonce, seal, self._clock.now()))
        return {"pres_id": pid, "nonce": nonce,
                "seal": seal, "fields": dict(fields)}

    def verify(self, pres_id, *, zid, fields, nonce,
               seal):
        """Verificacion en ORDEN correcto:
        1) comparar campos+nonce vs ALMACENADOS
        2) verificar sello HMAC (anti-alteracion)"""
        row = self._db.query_one(
            "SELECT fields_json, nonce, seal FROM"
            " zid_presentations WHERE pres_id = ?"
            " AND zid = ?",
            (str(pres_id), str(zid)))
        if row is None:
            return {"valid": False,
                    "reason": "no encontrada"}
        stored_fields = json.loads(
            str(row["fields_json"]))
        stored_nonce = str(row["nonce"])
        # PASO 1: comparar datos vs almacenados
        if fields != stored_fields:
            return {"valid": False,
                    "reason": "no coincide con la"
                              " presentacion original"
                              " (campos distintos)"}
        if str(nonce) != stored_nonce:
            return {"valid": False,
                    "reason": "no coincide con la"
                              " presentacion original"
                              " (nonce distinto)"}
        # PASO 2: verificar sello con los datos
        # ALMACENADOS (anti-alteracion post-emision)
        expected_seal = self._seal(
            zid, stored_fields, stored_nonce)
        if str(seal) != expected_seal:
            return {"valid": False,
                    "reason": "sello invalido"
                              " (alterada despues de"
                              " emitirse)"}
        self._db.execute(
            "UPDATE zid_presentations SET verified"
            " = 1 WHERE pres_id = ?",
            (str(pres_id),))
        return {"valid": True,
                "fields": dict(stored_fields)}

    def presentations_of(self, zid):
        rows = self._db.query_all(
            "SELECT pres_id, verified FROM"
            " zid_presentations WHERE zid = ?"
            " ORDER BY rowid", (str(zid),))
        return [{"pres_id": str(r["pres_id"]),
                 "verified": bool(
                     int(r["verified"]))}
                for r in rows]
