
"""Validacion de pagos NEXO (persistente, auditable).

Cada chequeo inserta su propia fila con validation_id
unico (la corrida completa comparte batch_id)."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_payment_validations", (
        "CREATE TABLE IF NOT EXISTS nexo_payment_validations (validation_id TEXT PRIMARY KEY, payment_ref TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', validated_at REAL NOT NULL)",
    )),
)

class NexoPaymentValidation:
    """Validaciones: monto, contraparte, referencia,
    moneda soportada (via currency gateway)."""

    def __init__(self, db, clock,
                 currency_gateway=None):
        self._db = db
        self._clock = clock
        self._cur = currency_gateway
        MigrationRunner(db, "nexo.payvalid",
                        _MIGRATIONS).run(clock)

    def validate_payment(self, *, amount,
                         currency="USD",
                         counterparty="",
                         reference="") -> dict:
        from decimal import Decimal as _D
        checks = []
        try:
            ok = _D(str(amount)) > 0
            detail = "monto=" + str(amount)
        except Exception:
            ok = False
            detail = "monto invalido"
        checks.append(("AMOUNT_POSITIVE", ok, detail))
        checks.append(("COUNTERPARTY_REQUIRED",
                       bool(counterparty.strip()),
                       "counterparty="
                       + (counterparty or "")))
        checks.append(("REFERENCE_REQUIRED",
                       bool(reference.strip()),
                       "reference="
                       + (reference or "")))
        cur_ok = True
        if self._cur is not None:
            cur_ok = currency in self._cur.supported()
        checks.append(("CURRENCY_SUPPORTED", cur_ok,
                       "currency=" + currency))
        batch_id = "PVAL-" + str(uuid.uuid4())
        passed = all(c[1] for c in checks)
        now = self._clock.now()
        ids = []
        with self._db.transaction() as cursor:
            for ctype, cok, cdetail in checks:
                vid = ("PVALC-"
                       + str(uuid.uuid4()))
                cursor.execute(
                    "INSERT INTO"
                    " nexo_payment_validations"
                    " (validation_id, payment_ref,"
                    " passed, detail, validated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (vid, ctype,
                     1 if cok else 0, cdetail,
                     now))
                ids.append(vid)
        return {"validation_id": batch_id,
                "row_ids": ids,
                "valid": passed,
                "checks": [{"check": c,
                            "passed": okk,
                            "detail": d}
                           for c, okk, d in checks]}
