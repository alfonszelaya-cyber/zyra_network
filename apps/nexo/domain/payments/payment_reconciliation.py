
"""Conciliacion de pagos NEXO: statement externo vs
pagos registrados, match por referencia y monto exacto
(Decimal). Persistente y auditable."""
from __future__ import annotations
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_payment_reconciliations", (
        "CREATE TABLE IF NOT EXISTS nexo_payment_reconciliations (reconciliation_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, matched INTEGER NOT NULL, unmatched INTEGER NOT NULL, detail_json TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL)",
    )),
)

class NexoPaymentReconciliation:
    """Conciliacion por referencia + monto exacto."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.payrecon",
                        _MIGRATIONS).run(clock)

    def reconcile(self, *, company_id, payments,
                  statement) -> dict:
        from decimal import Decimal as _D
        by_ref = {}
        for s in statement or []:
            by_ref[str(s.get("reference", ""))] = \
                _D(str(s.get("amount", "0")))
        matched, unmatched = [], []
        for p in payments or []:
            ref = str(p.get("reference", ""))
            amt = _D(str(p.get("amount", "0")))
            item = {"payment_id":
                    p.get("payment_id"),
                    "reference": ref}
            if ref in by_ref and by_ref[ref] == amt:
                matched.append(item)
            else:
                unmatched.append(item)
        rid = "REC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_payment_reconciliations"
                " (reconciliation_id, company_id,"
                " matched, unmatched, detail_json,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (rid, company_id, len(matched),
                 len(unmatched),
                 _j.dumps({"matched": matched,
                           "unmatched": unmatched},
                          default=str), now))
        return {"reconciliation_id": rid,
                "company_id": company_id,
                "matched": len(matched),
                "unmatched": len(unmatched),
                "items": {"matched": matched,
                          "unmatched": unmatched}}
