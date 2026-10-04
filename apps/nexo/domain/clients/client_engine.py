
# client_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_clients", ("CREATE TABLE IF NOT EXISTS nexo_clients (client_id TEXT PRIMARY KEY, name TEXT NOT NULL, document TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', phone TEXT, country TEXT NOT NULL DEFAULT 'N/A', client_type TEXT NOT NULL DEFAULT 'PERSON', status TEXT NOT NULL DEFAULT 'ACTIVE', risk_level TEXT NOT NULL DEFAULT 'NORMAL', financial_score INTEGER NOT NULL DEFAULT 0, fiscal_score INTEGER NOT NULL DEFAULT 0, operational_score INTEGER NOT NULL DEFAULT 0, zyra_score INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)",)),
)

class ClientEngine:
    """Motor central de clientes (persistente)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.clients",
                        _MIGRATIONS).run(clock)

    def create_client(self, *, name: str, document: str,
                      email: str, client_type: str = "PERSON",
                      country: str = "N/A",
                      phone: Optional[str] = None) -> dict:
        client_id = f"CLI-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_clients"
                " (client_id, name, document, email,"
                " phone, country, client_type, status,"
                " risk_level, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?,"
                " 'ACTIVE', 'NORMAL', ?, ?)",
                (client_id, name, document, email,
                 phone, country, client_type, now, now))
        return self.get_client(client_id)

    def update_client(self, client_id: str,
                      updates: Dict) -> Optional[dict]:
        client = self.get_client(client_id)
        if not client:
            return None
        sets = []
        params = []
        allowed = ("name", "email", "phone", "country",
                   "status", "risk_level",
                   "financial_score", "fiscal_score",
                   "operational_score", "zyra_score")
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)
        if not sets:
            return client
        sets.append("updated_at = ?")
        params.append(self._clock.now())
        params.append(client_id)
        self._db.execute(
            "UPDATE nexo_clients SET "
            + ", ".join(sets)
            + " WHERE client_id = ?", tuple(params))
        return self.get_client(client_id)

    def get_client(self, client_id: str) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_clients"
            " WHERE client_id = ?", (client_id,))
        return self._row(row) if row else None

    def get_all_clients(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_clients"
            " ORDER BY created_at")
        return [self._row(r) for r in rows]

    def _row(self, r) -> dict:
        return {"client_id": str(r["client_id"]),
                "name": str(r["name"]),
                "document": str(r["document"]),
                "email": str(r["email"]),
                "phone": (str(r["phone"])
                          if r["phone"] else None),
                "country": str(r["country"]),
                "client_type": str(r["client_type"]),
                "status": str(r["status"]),
                "risk_level": str(r["risk_level"]),
                "financial_score": int(r["financial_score"]),
                "fiscal_score": int(r["fiscal_score"]),
                "operational_score": int(r["operational_score"]),
                "zyra_score": int(r["zyra_score"]),
                "created_at": float(r["created_at"]),
                "updated_at": float(r["updated_at"])}

    def block_client(self, client_id: str) -> Optional[dict]:
        return self.update_client(client_id,
                                  {"status": "BLOCKED"})

    def activate_client(self, client_id: str) -> Optional[dict]:
        return self.update_client(client_id,
                                  {"status": "ACTIVE"})

    def update_risk_level(self, client_id: str,
                          risk_level: str) -> Optional[dict]:
        return self.update_client(client_id,
                                  {"risk_level": risk_level})

    def generate_summary(self) -> Dict:
        clients = self.get_all_clients()
        active = len([c for c in clients
                      if c["status"] == "ACTIVE"])
        blocked = len([c for c in clients
                       if c["status"] == "BLOCKED"])
        return {"total_clients": len(clients),
                "active_clients": active,
                "blocked_clients": blocked,
                "generated_at": self._clock.now()}
