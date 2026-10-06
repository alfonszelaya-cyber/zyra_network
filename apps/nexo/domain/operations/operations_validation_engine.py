
"""Operations Validation Engine - NEXO / ZYRA (migrado
mejorado). Validaciones de produccion: monto positivo
(Decimal), descripcion requerida. Persistidas con id
unico por fila (leccion NG1). El summary cuenta
chequeos individuales persistidos."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_operation_validations", (
        "CREATE TABLE IF NOT EXISTS nexo_operation_validations (validation_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, validation_type TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', validated_at REAL NOT NULL)",
    )),
)

class OperationsValidationEngine:
    """Validaciones de operaciones (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.opvalidations",
                        _MIGRATIONS).run(clock)

    def validate_operation(self, *, operation_id,
                           amount, description) -> dict:
        from decimal import Decimal as _D
        checks = []
        try:
            ok = _D(str(amount)) > 0
            detail = "monto=" + str(amount)
        except Exception:
            ok = False
            detail = "monto invalido"
        checks.append(("AMOUNT_POSITIVE", ok, detail))
        checks.append(("DESCRIPTION_REQUIRED",
                       bool(str(description).strip()),
                       "len="
                       + str(len(str(description)))))
        now = self._clock.now()
        ids = []
        with self._db.transaction() as cursor:
            for vtype, cok, cdetail in checks:
                vid = "VAL-" + str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO"
                    " nexo_operation_validations"
                    " (validation_id, operation_id,"
                    " validation_type, passed, detail,"
                    " validated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (vid, operation_id, vtype,
                     1 if cok else 0, cdetail, now))
                ids.append(vid)
        failed = [c for c in checks if not c[1]]
        return {"operation_id": operation_id,
                "row_ids": ids,
                "valid": len(failed) == 0,
                "checks": [{"check": c,
                            "passed": okk,
                            "detail": d}
                           for c, okk, d in checks]}

    def validations_of(self,
                       operation_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_operation_validations"
            " WHERE operation_id = ?"
            " ORDER BY validated_at", (operation_id,))
        return [{"validation_id":
                     str(r["validation_id"]),
                 "validation_type":
                     str(r["validation_type"]),
                 "passed": bool(r["passed"]),
                 "detail": str(r["detail"])}
                for r in rows]

    def summary(self) -> dict:
        row = self._db.query_one(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN passed = 1 THEN 1"
            " ELSE 0 END) AS ok FROM"
            " nexo_operation_validations")
        total = int(row["total"]) if row else 0
        ok = int(row["ok"] or 0) if row else 0
        return {"validations": total,
                "successful": ok,
                "failed": total - ok,
                "generated_at": self._clock.now()}
