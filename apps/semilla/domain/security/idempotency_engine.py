
"""Idempotency Engine SEMILLA (SM9). claim/
complete/replay/forget con TTL. Evita doble
ejecucion de operaciones criticas (pagos,
certificaciones, desembolsos)."""
from __future__ import annotations
import json as _j
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_idempotency", (
        "CREATE TABLE IF NOT EXISTS sm_idempotency (idem_key TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'default', result_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, PRIMARY KEY(idem_key, scope))",
    )),
)

class IdempotencyEngine:
    """Idempotencia por (key, scope) con TTL."""

    def __init__(self, db, clock,
                 ttl_seconds=86400):
        self._db = db
        self._clock = clock
        self._ttl = int(ttl_seconds)
        MigrationRunner(db, "sm.idem",
                        _MIGRATIONS).run(clock)

    def claim(self, *, key,
              scope="default") -> dict:
        now = self._clock.now()
        row = self._db.query_one(
            "SELECT * FROM sm_idempotency WHERE"
            " idem_key = ? AND scope = ?",
            (key, scope))
        if row is not None:
            age = (now
                   - float(row["created_at"]))
            if age <= self._ttl:
                return {"first": False,
                        "result": _j.loads(
                            str(row["result_json"]))}
            self._db.execute(
                "DELETE FROM sm_idempotency"
                " WHERE idem_key = ? AND"
                " scope = ?", (key, scope))
        return {"first": True, "result": None}

    def complete(self, *, key,
                 scope="default",
                 result=None) -> dict:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_idempotency"
                " (idem_key, scope,"
                " result_json, created_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(idem_key, scope)"
                " DO UPDATE SET result_json ="
                " excluded.result_json,"
                " created_at ="
                " excluded.created_at",
                (key, scope,
                 _j.dumps(result or {},
                          default=str), now))
        return {"key": key, "scope": scope,
                "stored": True}

    def forget(self, *, key,
               scope="default") -> dict:
        self._db.execute(
            "DELETE FROM sm_idempotency"
            " WHERE idem_key = ? AND scope = ?",
            (key, scope))
        return {"key": key, "scope": scope,
                "forgotten": True}
