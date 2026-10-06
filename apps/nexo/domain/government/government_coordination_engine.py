
"""Government Coordination Engine - coordinacion entre
instituciones (NG6). Solicitudes con respuesta y
cierre. Persistente."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_gov_coord_requests", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_coord_requests (request_id TEXT PRIMARY KEY, from_institution TEXT NOT NULL, to_institution TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', response TEXT, status TEXT NOT NULL DEFAULT 'SENT', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class GovernmentCoordinationEngine:
    """Solicitudes interinstitucionales."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govcoord",
                        _MIGRATIONS).run(clock)

    def send_request(self, *, from_institution,
                     to_institution, subject,
                     detail="") -> dict:
        rid = "GCR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_gov_coord_requests"
                " (request_id, from_institution,"
                " to_institution, subject, detail,"
                " response, status, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, ?, NULL,"
                " 'SENT', ?, ?)",
                (rid, from_institution,
                 to_institution, subject, detail,
                 now, now))
        return self.get_request(rid)

    def get_request(self,
                    request_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM"
            " nexo_gov_coord_requests WHERE"
            " request_id = ?", (request_id,))
        if not row:
            return None
        return {"request_id":
                    str(row["request_id"]),
                "from_institution":
                    str(row["from_institution"]),
                "to_institution":
                    str(row["to_institution"]),
                "subject": str(row["subject"]),
                "detail": str(row["detail"]),
                "response": (str(row["response"])
                             if row["response"]
                             else None),
                "status": str(row["status"]),
                "created_at":
                    float(row["created_at"])}

    def answer_request(self, *, request_id,
                       response) -> dict:
        row = self._db.query_one(
            "SELECT status FROM"
            " nexo_gov_coord_requests WHERE"
            " request_id = ?", (request_id,))
        if not row:
            raise KeyError(request_id)
        if str(row["status"]) != "SENT":
            raise ValueError(
                "solo SENT se responde")
        now = self._clock.now()
        self._db.execute(
            "UPDATE nexo_gov_coord_requests SET"
            " response = ?, status = 'ANSWERED',"
            " updated_at = ? WHERE request_id = ?",
            (response, now, request_id))
        return self.get_request(request_id)

    def inbox_of(self, institution_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT request_id FROM"
            " nexo_gov_coord_requests WHERE"
            " to_institution = ?"
            " ORDER BY created_at DESC",
            (institution_id,))
        return [self.get_request(
            str(r["request_id"]))
            for r in rows]

    def sent_by(self, institution_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT request_id FROM"
            " nexo_gov_coord_requests WHERE"
            " from_institution = ?"
            " ORDER BY created_at DESC",
            (institution_id,))
        return [self.get_request(
            str(r["request_id"]))
            for r in rows]
