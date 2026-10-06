
"""Government Document Engine - documentos oficiales
(NG6). Registro con hash SHA-256 del contenido para
verificacion de integridad local."""
from __future__ import annotations
from typing import List, Optional
import hashlib
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_gov_documents", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_documents (doc_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, doc_type TEXT NOT NULL, title TEXT NOT NULL, content_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'REGISTERED', created_at REAL NOT NULL)",
    )),
)

class GovernmentDocumentEngine:
    """Documentos oficiales con hash de integridad."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govdoc",
                        _MIGRATIONS).run(clock)

    @staticmethod
    def _hash(content) -> str:
        return hashlib.sha256(
            str(content).encode("utf-8")
            ).hexdigest()

    def register_document(self, *,
                          institution_id, doc_type,
                          title,
                          content) -> dict:
        did = "GDOC-" + str(uuid.uuid4())
        now = self._clock.now()
        h = self._hash(content)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_gov_documents"
                " (doc_id, institution_id,"
                " doc_type, title, content_hash,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " 'REGISTERED', ?)",
                (did, institution_id, doc_type,
                 title, h, now))
        return {"doc_id": did,
                "institution_id":
                    institution_id,
                "doc_type": doc_type,
                "title": title,
                "content_hash": h,
                "status": "REGISTERED"}

    def get_document(self,
                     doc_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_gov_documents"
            " WHERE doc_id = ?", (doc_id,))
        if not row:
            return None
        return {"doc_id": str(row["doc_id"]),
                "institution_id":
                    str(row["institution_id"]),
                "doc_type": str(row["doc_type"]),
                "title": str(row["title"]),
                "content_hash":
                    str(row["content_hash"]),
                "status": str(row["status"]),
                "created_at":
                    float(row["created_at"])}

    def verify_document(self, doc_id,
                        content) -> bool:
        doc = self.get_document(doc_id)
        if not doc:
            return False
        return (doc["content_hash"]
                == self._hash(content))

    def documents_of(self,
                     institution_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT doc_id FROM"
            " nexo_gov_documents WHERE"
            " institution_id = ?"
            " ORDER BY created_at",
            (institution_id,))
        return [self.get_document(
            str(r["doc_id"])) for r in rows]
