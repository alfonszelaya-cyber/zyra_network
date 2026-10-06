
"""Recurring Entries Engine - asientos recurrentes
(NG3). Total SIEMPRE con 2 decimales."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

FREQUENCIES = ("MONTHLY", "WEEKLY", "YEARLY")

_MIGRATIONS = (
    Migration(1, "nexo_recurring_entries", (
        "CREATE TABLE IF NOT EXISTS nexo_recurring_entries (template_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, name TEXT NOT NULL, frequency TEXT NOT NULL, lines_json TEXT NOT NULL DEFAULT '[]', source_ref TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, run_count INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)

class RecurringEntriesEngine:
    """Asientos recurrentes (plantillas persistidas)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.recurring",
                        _MIGRATIONS).run(clock)

    def create_template(self, *, company_id, name,
                        frequency, lines,
                        source_ref="") -> dict:
        from decimal import Decimal as _D
        td = sum((_D(str(l.get("debit", "0")))
                  for l in lines), _D("0"))
        tc = sum((_D(str(l.get("credit", "0")))
                  for l in lines), _D("0"))
        if td != tc:
            raise ValueError(
                "plantilla descuadrada: D="
                + str(td) + " C=" + str(tc))
        if frequency not in FREQUENCIES:
            frequency = "MONTHLY"
        tid = "REC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_recurring_entries"
                " (template_id, company_id, name,"
                " frequency, lines_json, source_ref,"
                " active, run_count, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)",
                (tid, company_id, name, frequency,
                 _j.dumps(lines, default=str),
                 source_ref, now))
        return {"template_id": tid,
                "company_id": company_id,
                "name": name,
                "frequency": frequency,
                "total": str(td.quantize(_D("0.01"))),
                "active": True}

    def get_template(self,
                     template_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_recurring_entries"
            " WHERE template_id = ?", (template_id,))
        if not row:
            return None
        return {"template_id":
                    str(row["template_id"]),
                "company_id": str(row["company_id"]),
                "name": str(row["name"]),
                "frequency": str(row["frequency"]),
                "lines": _j.loads(
                    str(row["lines_json"])),
                "source_ref": str(row["source_ref"]),
                "active": bool(row["active"]),
                "run_count": int(row["run_count"])}

    def run_template(self, template_id) -> dict:
        t = self.get_template(template_id)
        if not t or not t["active"]:
            raise ValueError(
                "plantilla inactiva/inexistente")
        self._db.execute(
            "UPDATE nexo_recurring_entries SET"
            " run_count = run_count + 1"
            " WHERE template_id = ?", (template_id,))
        t2 = self.get_template(template_id)
        return {"template_id": template_id,
                "lines": t["lines"],
                "run_count": t2["run_count"]}

    def deactivate(self, template_id) -> dict:
        self._db.execute(
            "UPDATE nexo_recurring_entries SET"
            " active = 0 WHERE template_id = ?",
            (template_id,))
        return self.get_template(template_id)

    def templates_of(self,
                     company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT template_id, name, frequency,"
            " active, run_count FROM"
            " nexo_recurring_entries WHERE"
            " company_id = ? ORDER BY created_at",
            (company_id,))
        return [{"template_id": str(r["template_id"]),
                 "name": str(r["name"]),
                 "frequency": str(r["frequency"]),
                 "active": bool(r["active"]),
                 "run_count": int(r["run_count"])}
                for r in rows]
