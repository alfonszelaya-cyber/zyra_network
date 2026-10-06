
"""Institution Registry - centros educativos (SM1)."""
from __future__ import annotations
from typing import List, Optional
import uuid
import json as _j
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_institutions", (
        "CREATE TABLE IF NOT EXISTS sm_institutions (institution_id TEXT PRIMARY KEY, name TEXT NOT NULL, mined_code TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT 'SV', district TEXT NOT NULL DEFAULT '', levels_json TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
)

class InstitutionRegistryEngine:
    """Registro de instituciones educativas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.institution",
                        _MIGRATIONS).run(clock)

    def register(self, *, name, mined_code="",
                 country="SV", district="",
                 levels=None) -> dict:
        if not str(name).strip():
            raise ValueError("name requerido")
        iid = "SMINST-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_institutions"
                " (institution_id, name,"
                " mined_code, country, district,"
                " levels_json, active, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (iid, str(name).strip(),
                 str(mined_code), country,
                 str(district),
                 _j.dumps(levels or [],
                          default=str), now))
        return self.get(iid)

    def get(self, institution_id
            ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_institutions"
            " WHERE institution_id = ?",
            (institution_id,))
        if not row:
            return None
        return {"institution_id":
                    str(row["institution_id"]),
                "name": str(row["name"]),
                "mined_code":
                    str(row["mined_code"]),
                "country": str(row["country"]),
                "district": str(row["district"]),
                "levels": _j.loads(
                    str(row["levels_json"])),
                "active": bool(row["active"])}

    def list_all(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT institution_id FROM"
            " sm_institutions WHERE active = 1"
            " ORDER BY name")
        return [self.get(
            str(r["institution_id"]))
            for r in rows]
