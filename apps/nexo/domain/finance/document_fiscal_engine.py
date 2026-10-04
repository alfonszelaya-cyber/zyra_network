
# document_fiscal_engine.py - NEXO / ZYRA (v7, SQL 1-linea)
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "fiscal_documents", (
        "CREATE TABLE IF NOT EXISTS fiscal_documents (document_id TEXT PRIMARY KEY, document_json TEXT NOT NULL, pais TEXT NOT NULL DEFAULT '', cliente_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ISSUED', created_at REAL NOT NULL)",
    )),
    Migration(2, "fiscal_simulations", (
        "CREATE TABLE IF NOT EXISTS fiscal_simulations (simulation_id TEXT PRIMARY KEY, simulation_json TEXT NOT NULL, created_at REAL NOT NULL)",
    )),
)

class FiscalDocumentEngine:
    """Documentos fiscales."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fiscaldoc",
                        _MIGRATIONS).run(clock)

    def simular_documento(self, document: Dict) -> Dict:
        import json as _j
        total = (document.get("totales", {})
                 .get("total", 0))
        valid = True
        risk = "LOW"
        observations = []
        try:
            if float(total) <= 0:
                valid = False
                risk = "HIGH"
                observations.append("INVALID_TOTAL")
        except Exception:
            valid = False
            risk = "HIGH"
            observations.append("INVALID_TOTAL")
        sid = f"SIM-{uuid.uuid4()}"
        record = {"simulation_id": sid,
                  "created_at": self._clock.now(),
                  "valid": valid, "risk": risk,
                  "observations": observations,
                  "preview": document}
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO fiscal_simulations"
                " (simulation_id, simulation_json,"
                " created_at) VALUES (?, ?, ?)",
                (sid, _j.dumps(record, default=str),
                 self._clock.now()))
        return record

    def generar_documento(self, document: Dict) -> Dict:
        import json as _j
        did = f"DOC-{uuid.uuid4()}"
        now = self._clock.now()
        pais = str(document.get("pais", ""))
        cliente = str((document.get("cliente", {})
                       .get("id", "")))
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO fiscal_documents"
                " (document_id, document_json,"
                " pais, cliente_id, status, created_at)"
                " VALUES (?, ?, ?, ?, 'ISSUED', ?)",
                (did, _j.dumps(document, default=str),
                 pais, cliente, now))
        return {"document_id": did,
                "created_at": now,
                "status": "ISSUED",
                "document": document}

    def get_all_documents(self) -> List[Dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM fiscal_documents"
            " ORDER BY created_at")
        return [{"document_id": str(r["document_id"]),
                 "created_at": float(r["created_at"]),
                 "status": str(r["status"]),
                 "document": _j.loads(
                     str(r["document_json"]))}
                for r in rows]

    def get_document(self, document_id: str) -> Optional[Dict]:
        for d in self.get_all_documents():
            if d["document_id"] == document_id:
                return d
        return None

    def get_summary(self) -> Dict:
        return {"documents": len(self.get_all_documents()),
                "generated_at": self._clock.now()}
