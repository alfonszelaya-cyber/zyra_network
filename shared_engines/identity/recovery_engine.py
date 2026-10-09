"""ZID Recovery Engine (ID-13) - codigos de
recuperacion para un ZID: N codigos de UNA vez
(se muestran SOLO al emitir, se guardan
hasheados - regla 63), con expiracion.
Reglas 63/66/76."""
from __future__ import annotations
import hashlib, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_recovery", (
        "CREATE TABLE IF NOT EXISTS zid_recovery ("
        " code_id TEXT PRIMARY KEY, zid TEXT NOT NULL,"
        " code_hash TEXT NOT NULL, expires_at REAL NOT"
        " NULL, used INTEGER NOT NULL DEFAULT 0,"
        " created_at REAL NOT NULL)",
        "CREATE INDEX ix_rec_zid ON zid_recovery"
        " (zid)",
    )),
)


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class ZidRecoveryEngine:
    """Codigos de recuperacion de un ZID."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.recovery",
                        _MIGRATIONS).run(clock)

    def issue_codes(self, *, zid, count=3,
                    ttl_seconds=2592000.0):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        if int(count) < 1 or int(count) > 10:
            raise ValueError("count 1..10")
        now = self._clock.now()
        exp = now + float(ttl_seconds)
        clear = []
        for _ in range(int(count)):
            code = ("ZREC-"
                    + uuid.uuid4().hex[:12])
            self._db.execute(
                "INSERT INTO zid_recovery (code_id,"
                " zid, code_hash, expires_at, used,"
                " created_at) VALUES (?, ?, ?, ?, 0, ?)",
                ("ZRC-" + uuid.uuid4().hex[:10],
                 str(zid), _sha(code), exp, now))
            clear.append(code)
        return {"codes": clear,
                "note": "guarde estos codigos:"
                        " no se vuelven a mostrar"
                        " (regla 63)"}

    def recover(self, *, zid, code):
        now = self._clock.now()
        row = self._db.query_one(
            "SELECT code_id, expires_at, used FROM"
            " zid_recovery WHERE zid = ? AND"
            " code_hash = ?",
            (str(zid), _sha(str(code))))
        if row is None:
            return {"ok": False,
                    "reason": "codigo invalido"}
        if int(row["used"]) == 1:
            return {"ok": False,
                    "reason": "codigo ya usado"}
        if float(row["expires_at"]) <= now:
            return {"ok": False,
                    "reason": "codigo expirado"}
        self._db.execute(
            "UPDATE zid_recovery SET used = 1 WHERE"
            " code_id = ?", (str(row["code_id"]),))
        return {"ok": True, "zid": str(zid)}

    def valid_remaining(self, zid):
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM zid_recovery"
            " WHERE zid = ? AND used = 0 AND"
            " expires_at > ?",
            (str(zid), self._clock.now()))
        return int(row["n"])
