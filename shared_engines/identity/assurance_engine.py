"""Identity Assurance Engine (ID-1) - niveles L0..L3
por evidencia. Reglas 63/66/76."""
from __future__ import annotations
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_assurance", (
        "CREATE TABLE IF NOT EXISTS zid_assurance ("
        " zid TEXT PRIMARY KEY, level TEXT NOT NULL,"
        " evidence_json TEXT NOT NULL DEFAULT '[]',"
        " updated_at REAL NOT NULL)",
    )),
)


class AssuranceEngine:
    """Niveles de assurance por evidencia (ID-1)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.assurance",
                        _MIGRATIONS).run(clock)

    def compute(self, *, zid, has_active_zid=False,
                has_biometrics=False,
                has_official_doc=False):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        level = "L0"
        evid = []
        if has_active_zid:
            level = "L1"
            evid.append("zid_activo")
        if has_biometrics:
            level = "L2"
            evid.append("biometria")
        if has_official_doc and has_biometrics:
            level = "L3"
            evid.append("documento_oficial")
        self._db.execute(
            "INSERT OR REPLACE INTO zid_assurance"
            " (zid, level, evidence_json, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (str(zid), level, str(evid),
             self._clock.now()))
        return {"zid": str(zid), "level": level,
                "evidence": evid}

    def level_of(self, zid):
        row = self._db.query_one(
            "SELECT level FROM zid_assurance WHERE"
            " zid = ?", (str(zid),))
        if row is None:
            return {"zid": str(zid), "level": "L0",
                    "note": "sin evidencia"}
        return {"zid": str(zid),
                "level": str(row["level"])}
