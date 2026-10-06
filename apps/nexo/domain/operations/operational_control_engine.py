
"""Operational Control Engine - NEXO / ZYRA (migrado
mejorado). Controles de produccion sobre operaciones:
limite de monto (Decimal) y anti-duplicado por
fingerprint. Persistente y auditable."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

CONTROL_TYPES = ("AMOUNT_LIMIT", "PERMISSION",
                 "DUPLICATE", "CONSISTENCY", "CUSTOM")

_MIGRATIONS = (
    Migration(1, "nexo_operation_controls", (
        "CREATE TABLE IF NOT EXISTS nexo_operation_controls (control_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, control_type TEXT NOT NULL, rule TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'PENDING', passed INTEGER, result_json TEXT NOT NULL DEFAULT '{}', checked_at REAL, created_at REAL NOT NULL)",
    )),
)

class OperationalControlEngine:
    """Controles operativos (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.opcontrols",
                        _MIGRATIONS).run(clock)

    def register_control(self, *, operation_id,
                         control_type, rule="") -> dict:
        if control_type not in CONTROL_TYPES:
            control_type = "CUSTOM"
        cid = "CTRL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_operation_controls"
                " (control_id, operation_id,"
                " control_type, rule, status, passed,"
                " result_json, checked_at, created_at)"
                " VALUES (?, ?, ?, ?, 'PENDING', NULL,"
                " '{}', NULL, ?)",
                (cid, operation_id, control_type,
                 rule, now))
        return {"control_id": cid,
                "operation_id": operation_id,
                "control_type": control_type,
                "rule": rule, "status": "PENDING"}

    def check_amount_limit(self, *, control_id,
                           amount, limit) -> dict:
        from decimal import Decimal as _D
        a = _D(str(amount))
        l = _D(str(limit))
        ok = a <= l
        now = self._clock.now()
        self._db.execute(
            "UPDATE nexo_operation_controls SET"
            " status = 'CHECKED', passed = ?,"
            " result_json = ?, checked_at = ?"
            " WHERE control_id = ?",
            (1 if ok else 0,
             _j.dumps({"amount": str(a),
                       "limit": str(l),
                       "passed": ok}), now,
             control_id))
        return {"control_id": control_id,
                "passed": ok,
                "amount": str(a), "limit": str(l)}

    def check_duplicate(self, *, control_id,
                        fingerprint,
                        previous_fingerprints) -> dict:
        ok = fingerprint not in (
            previous_fingerprints or [])
        now = self._clock.now()
        self._db.execute(
            "UPDATE nexo_operation_controls SET"
            " status = 'CHECKED', passed = ?,"
            " result_json = ?, checked_at = ?"
            " WHERE control_id = ?",
            (1 if ok else 0,
             _j.dumps({"fingerprint": fingerprint,
                       "duplicate": not ok}), now,
             control_id))
        return {"control_id": control_id,
                "passed": ok,
                "duplicate": not ok}

    def controls_of(self,
                    operation_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_operation_controls"
            " WHERE operation_id = ?"
            " ORDER BY created_at", (operation_id,))
        return [{"control_id": str(r["control_id"]),
                 "control_type": str(r["control_type"]),
                 "rule": str(r["rule"]),
                 "status": str(r["status"]),
                 "passed": (bool(r["passed"])
                            if r["passed"]
                            is not None else None)}
                for r in rows]

    def all_passed(self, operation_id) -> bool:
        rows = self._db.query_all(
            "SELECT passed, status FROM"
            " nexo_operation_controls"
            " WHERE operation_id = ?", (operation_id,))
        if not rows:
            return True
        for r in rows:
            if str(r["status"]) == "PENDING":
                return False
            if not r["passed"]:
                return False
        return True
