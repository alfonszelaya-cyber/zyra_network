
"""Gateway NEXO -> AuditTrail transversal (regla 69).

Firma real: append(*, event_type, actor, subject,
payload) -> AuditRecord. Se intenta primero con esa
firma exacta; si no hay trail, buffer local marcado.
Cada registro lleva quien/que/cuando/antes-despues."""
from __future__ import annotations
from typing import List
import json as _j
import uuid

class NexoAuditGateway:
    """Adaptador de auditoria NEXO."""

    def __init__(self, trail=None, db=None, clock=None):
        self._clock = clock
        self._trail = trail
        self._buffer = []
        if self._trail is None and db is not None:
            try:
                from shared_engines.audit.chain import (
                    AuditTrail)
                try:
                    self._trail = AuditTrail(db)
                except TypeError:
                    self._trail = None
            except Exception:
                self._trail = None

    @property
    def mode(self) -> str:
        return ("shared_audit"
                if self._trail is not None
                else "local_buffer")

    def record_event(self, *, event, actor="",
                     entity="", before=None,
                     after=None) -> dict:
        rec = {"audit_id": "NAUD-" + str(uuid.uuid4()),
               "event": event, "actor": actor,
               "entity": entity, "before": before,
               "after": after,
               "ts": (self._clock.now()
                      if self._clock is not None
                      else None)}
        sent = False
        if self._trail is not None:
            try:
                self._trail.append(
                    event_type=str(event),
                    actor=str(actor),
                    subject=str(entity),
                    payload=rec)
                sent = True
            except Exception:
                for name in ("record", "add", "log"):
                    m = getattr(self._trail, name,
                                None)
                    if callable(m):
                        try:
                            m(rec)
                            sent = True
                            break
                        except Exception:
                            continue
        if not sent:
            self._buffer.append(rec)
        return {"audit_id": rec["audit_id"],
                "recorded": True,
                "sent_to_network": sent,
                "mode": self.mode}

    def entries(self) -> List[dict]:
        return list(self._buffer)
