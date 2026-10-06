
"""Motor de auditoria de dominio NEXO.

Regla 69: el motor criptografico vive en
shared_engines.audit; NEXO mantiene su registro de
dominio (quien/que/cuando/antes-despues) y lo replica
al AuditTrail transversal via gateway cuando existe."""
from __future__ import annotations
from typing import List
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_audit_events", (
        "CREATE TABLE IF NOT EXISTS nexo_audit_events (audit_id TEXT PRIMARY KEY, event TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', entity TEXT NOT NULL DEFAULT '', before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)",
    )),
)

class NexoAuditEngine:
    """Auditoria de dominio persistente + replicacion."""

    def __init__(self, db, clock, gateway=None):
        self._db = db
        self._clock = clock
        self._gw = gateway
        MigrationRunner(db, "nexo.audit",
                        _MIGRATIONS).run(clock)

    def audit(self, *, event, actor="", entity="",
              before=None, after=None) -> dict:
        aid = "AUD-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_audit_events"
                " (audit_id, event, actor, entity,"
                " before_json, after_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (aid, event, actor, entity,
                 _j.dumps(before or {}, default=str),
                 _j.dumps(after or {}, default=str),
                 now))
        sent = None
        if self._gw is not None:
            sent = self._gw.record_event(
                event=event, actor=actor,
                entity=entity, before=before,
                after=after)
        return {"audit_id": aid, "event": event,
                "actor": actor, "entity": entity,
                "replicated": bool(
                    sent and sent.get("recorded"))}

    def history(self, entity="", actor="",
                limit=200) -> List[dict]:
        if entity:
            rows = self._db.query_all(
                "SELECT * FROM nexo_audit_events"
                " WHERE entity = ?"
                " ORDER BY created_at DESC LIMIT ?",
                (entity, limit))
        elif actor:
            rows = self._db.query_all(
                "SELECT * FROM nexo_audit_events"
                " WHERE actor = ?"
                " ORDER BY created_at DESC LIMIT ?",
                (actor, limit))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_audit_events"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,))
        return [{"audit_id": str(r["audit_id"]),
                 "event": str(r["event"]),
                 "actor": str(r["actor"]),
                 "entity": str(r["entity"]),
                 "before": _j.loads(
                     str(r["before_json"])),
                 "after": _j.loads(
                     str(r["after_json"])),
                 "created_at": float(r["created_at"])}
                for r in rows]
