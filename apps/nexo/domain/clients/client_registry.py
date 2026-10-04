
# client_registry.py - NEXO / ZYRA (v2: respeta client_id)
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "client_registry", ("CREATE TABLE IF NOT EXISTS client_registry (client_id TEXT PRIMARY KEY, client_json TEXT NOT NULL, total_transactions INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)",)),
    Migration(2, "client_registry_history", ("CREATE TABLE IF NOT EXISTS client_registry_history (history_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, event_type TEXT NOT NULL, description TEXT NOT NULL, created_at REAL NOT NULL)",)),
    Migration(3, "client_registry_links", ("CREATE TABLE IF NOT EXISTS client_registry_links (link_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, company_id TEXT NOT NULL, created_at REAL NOT NULL)",)),
)

class ClientRegistry:
    """Registro central de clientes."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.clientregistry",
                        _MIGRATIONS).run(clock)

    def store(self, client: Dict) -> Dict:
        import json as _j
        client_id = client.get("client_id")
        if not client_id:
            client_id = f"CLI-{uuid.uuid4()}"
            client["client_id"] = client_id
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO client_registry"
                " (client_id, client_json,"
                " total_transactions, created_at, updated_at)"
                " VALUES (?, ?, COALESCE("
                " (SELECT total_transactions FROM"
                "  client_registry WHERE client_id = ?),"
                " 0), COALESCE((SELECT created_at FROM"
                " client_registry WHERE client_id = ?), ?), ?)",
                (client_id,
                 _j.dumps(client, default=str),
                 client_id, client_id, now, now))
        return client

    def get_by_id(self, client_id: str) -> Optional[Dict]:
        import json as _j
        row = self._db.query_one(
            "SELECT * FROM client_registry"
            " WHERE client_id = ?", (client_id,))
        if not row:
            return None
        client = _j.loads(str(row["client_json"]))
        client["total_transactions"] = int(
            row["total_transactions"])
        return client

    def update(self, client_id: str,
               updates: Dict) -> Optional[Dict]:
        client = self.get_by_id(client_id)
        if not client:
            return None
        client.update(updates)
        import json as _j
        self._db.execute(
            "UPDATE client_registry SET"
            " client_json = ?, updated_at = ?"
            " WHERE client_id = ?",
            (_j.dumps(client, default=str),
             self._clock.now(), client_id))
        return client

    def link_company(self, *, client_id: str,
                     company_id: str) -> Dict:
        link_id = f"LNK-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO client_registry_links"
                " (link_id, client_id, company_id,"
                " created_at) VALUES (?, ?, ?, ?)",
                (link_id, client_id, company_id, now))
        return {"client_id": client_id,
                "company_id": company_id,
                "link_id": link_id,
                "status": "LINKED"}

    def register_history(self, *, client_id: str,
                         history_event: Dict) -> Dict:
        hid = f"H-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO client_registry_history"
                " (history_id, client_id, event_type,"
                " description, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (hid, client_id,
                 str(history_event.get("event_type", "")),
                 str(history_event.get("description", "")),
                 now))
        return history_event

    def bump_transactions(self, client_id: str) -> None:
        self._db.execute(
            "UPDATE client_registry SET"
            " total_transactions = total_transactions + 1"
            " WHERE client_id = ?", (client_id,))
