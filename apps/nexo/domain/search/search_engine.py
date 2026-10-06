
"""Nexo Search Engine - indice de busqueda (NG7)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ENTITY_TYPES = ("COMPANY", "OPERATION", "DOCUMENT",
                "INVOICE", "PAYMENT", "TICKET",
                "REPORT", "GENERAL")

_MIGRATIONS = (
    Migration(1, "nexo_search_index", (
        "CREATE TABLE IF NOT EXISTS nexo_search_index (doc_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL DEFAULT 'GENERAL', entity_ref TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', company_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class NexoSearchEngine:
    """Indice y busqueda por terminos con puntaje."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.search",
                        _MIGRATIONS).run(clock)

    def index(self, *, entity_ref, title,
              content="", entity_type="GENERAL",
              company_id="") -> dict:
        if entity_type not in ENTITY_TYPES:
            entity_type = "GENERAL"
        did = "IDX-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_search_index"
                " (doc_id, entity_type, entity_ref,"
                " title, content, company_id,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (did, entity_type, entity_ref,
                 title, content, company_id, now))
        return {"doc_id": did,
                "entity_type": entity_type,
                "entity_ref": entity_ref,
                "title": title}

    def search(self, query, entity_type="",
               limit=20) -> List[dict]:
        terms = [t for t in str(query).lower().split()
                 if t]
        if not terms:
            return []
        rows = self._db.query_all(
            "SELECT * FROM nexo_search_index"
            " ORDER BY created_at DESC LIMIT 500")
        hits = []
        for r in rows:
            if (entity_type
                    and str(r["entity_type"])
                    != entity_type):
                continue
            text = (str(r["title"]) + " "
                    + str(r["content"])).lower()
            score = sum(1 for t in terms
                        if t in text)
            if score > 0:
                hits.append({
                    "doc_id": str(r["doc_id"]),
                    "entity_type":
                        str(r["entity_type"]),
                    "entity_ref":
                        str(r["entity_ref"]),
                    "title": str(r["title"]),
                    "score": score})
        hits.sort(key=lambda h: -h["score"])
        return hits[:limit]

    def remove(self, entity_ref) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS c FROM"
            " nexo_search_index WHERE"
            " entity_ref = ?", (entity_ref,))
        n = int(row["c"]) if row else 0
        self._db.execute(
            "DELETE FROM nexo_search_index WHERE"
            " entity_ref = ?", (entity_ref,))
        return n
