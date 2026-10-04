
# declaration_engine.py - NEXO / ZYRA (v7, SQL 1-linea)
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "fiscal_declarations", (
        "CREATE TABLE IF NOT EXISTS fiscal_declarations (declaration_id TEXT PRIMARY KEY, declaration_json TEXT NOT NULL, declaration_type TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'REGISTERED', created_at REAL NOT NULL)",
    )),
)

class DeclarationEngine:
    """Motor de declaraciones fiscales."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.declaration",
                        _MIGRATIONS).run(clock)

    def add_declaration(self, declaration: Dict) -> Dict:
        import json as _j
        did = f"DEC-{uuid.uuid4()}"
        now = self._clock.now()
        dtype = str(declaration.get("type", ""))
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO fiscal_declarations"
                " (declaration_id, declaration_json,"
                " declaration_type, status, created_at)"
                " VALUES (?, ?, ?, 'REGISTERED', ?)",
                (did, _j.dumps(declaration, default=str),
                 dtype, now))
        return {"declaration_id": did,
                "declaration": declaration,
                "status": "REGISTERED",
                "created_at": now}

    def get_all_declarations(self) -> List[Dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM fiscal_declarations"
            " ORDER BY created_at")
        return [{"declaration_id": str(r["declaration_id"]),
                 "declaration": _j.loads(
                     str(r["declaration_json"])),
                 "status": str(r["status"]),
                 "created_at": float(r["created_at"])}
                for r in rows]

    def get_declaration(self, declaration_id: str) -> Optional[Dict]:
        for d in self.get_all_declarations():
            if d["declaration_id"] == declaration_id:
                return d
        return None

    def get_declarations_by_type(self, declaration_type: str) -> List[Dict]:
        return [d for d in self.get_all_declarations()
                if d["declaration"].get("type")
                == declaration_type]

    def get_summary(self) -> Dict:
        return {"total_declarations":
                len(self.get_all_declarations()),
                "generated_at": self._clock.now()}

    def generate_report(self) -> Dict:
        return {"report_type": "FISCAL_DECLARATIONS",
                "records": len(self.get_all_declarations()),
                "summary": self.get_summary(),
                "generated_at": self._clock.now()}
