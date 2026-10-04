
# client_relationship_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_client_relationships", ("CREATE TABLE IF NOT EXISTS nexo_client_relationships (relationship_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, company_id TEXT NOT NULL, relationship TEXT NOT NULL DEFAULT 'OWNER', ownership_percentage REAL NOT NULL DEFAULT 100.0, status TEXT NOT NULL DEFAULT 'LINKED', created_at REAL NOT NULL, updated_at REAL)",)),
)

class ClientRelationshipEngine:
    """Motor de relaciones cliente-empresa (persistente)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.clientrel",
                        _MIGRATIONS).run(clock)

    def link_company(self, client_id: str, company_id: str,
                     relationship: str = "OWNER",
                     ownership_percentage: float = 100.0) -> dict:
        rel_id = f"REL-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_client_relationships"
                " (relationship_id, client_id, company_id,"
                " relationship, ownership_percentage,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, 'LINKED', ?)",
                (rel_id, client_id, company_id,
                 relationship, ownership_percentage, now))
        return {"relationship_id": rel_id,
                "client_id": client_id,
                "company_id": company_id,
                "relationship": relationship,
                "ownership_percentage": ownership_percentage,
                "status": "LINKED",
                "created_at": now}

    def get_relationship(self, relationship_id: str) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_client_relationships"
            " WHERE relationship_id = ?", (relationship_id,))
        return self._row(row) if row else None

    def get_client_relationships(self, client_id: str) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_client_relationships"
            " WHERE client_id = ?", (client_id,))
        return [self._row(r) for r in rows]

    def get_company_relationships(self, company_id: str) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_client_relationships"
            " WHERE company_id = ?", (company_id,))
        return [self._row(r) for r in rows]

    def _row(self, r) -> dict:
        return {"relationship_id": str(r["relationship_id"]),
                "client_id": str(r["client_id"]),
                "company_id": str(r["company_id"]),
                "relationship": str(r["relationship"]),
                "ownership_percentage": float(r["ownership_percentage"]),
                "status": str(r["status"]),
                "created_at": float(r["created_at"])}

    def unlink_company(self, relationship_id: str) -> Optional[dict]:
        rel = self.get_relationship(relationship_id)
        if not rel:
            return None
        self._db.execute(
            "UPDATE nexo_client_relationships"
            " SET status = 'UNLINKED', updated_at = ?"
            " WHERE relationship_id = ?",
            (self._clock.now(), relationship_id))
        return self.get_relationship(relationship_id)

    def suspend_relationship(self, relationship_id: str) -> Optional[dict]:
        rel = self.get_relationship(relationship_id)
        if not rel:
            return None
        self._db.execute(
            "UPDATE nexo_client_relationships"
            " SET status = 'SUSPENDED', updated_at = ?"
            " WHERE relationship_id = ?",
            (self._clock.now(), relationship_id))
        return self.get_relationship(relationship_id)

    def link_owner(self, client_id, company_id, percentage):
        return self.link_company(client_id, company_id,
                                 "OWNER", percentage)

    def link_legal_representative(self, client_id, company_id):
        return self.link_company(client_id, company_id,
                                 "LEGAL_REPRESENTATIVE", 0)

    def link_shareholder(self, client_id, company_id, percentage):
        return self.link_company(client_id, company_id,
                                 "SHAREHOLDER", percentage)

    def link_beneficiary(self, client_id, company_id):
        return self.link_company(client_id, company_id,
                                 "BENEFICIARY", 0)

    def generate_summary(self) -> dict:
        rows = self._db.query_all(
            "SELECT status, COUNT(*) AS n FROM"
            " nexo_client_relationships GROUP BY status")
        total = sum(int(r["n"]) for r in rows)
        active = sum(int(r["n"]) for r in rows
                     if r["status"] == "LINKED")
        return {"relationships": total,
                "active_relationships": active,
                "generated_at": self._clock.now()}
