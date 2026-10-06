
"""Message bus SEMILLA (regla 69)."""
from __future__ import annotations
from typing import List
import json as _j

class SemillaMessageBus:
    """Bus interno SEMILLA."""

    def __init__(self, outbox=None, clock=None):
        self._outbox = outbox
        self._clock = clock
        self._buffer = []

    def _publish_external(self, event) -> bool:
        if self._outbox is None:
            return False
        for name in ("append", "enqueue",
                     "publish", "put", "add"):
            m = getattr(self._outbox, name,
                        None)
            if callable(m):
                try:
                    m(event)
                    return True
                except TypeError:
                    try:
                        m(_j.dumps(event,
                                   default=str))
                        return True
                    except Exception:
                        return False
                except Exception:
                    return False
        return False

    def publish(self, event) -> dict:
        delivered = self._publish_external(event)
        if not delivered:
            self._buffer.append(event)
        return {"event_id":
                    event.get("event_id"),
                "event": event.get("event"),
                "delivered_to_network":
                    delivered,
                "buffered": not delivered}

    def drain(self, limit=100) -> List[dict]:
        taken = self._buffer[:limit]
        self._buffer = self._buffer[limit:]
        return taken

    def pending(self) -> int:
        return len(self._buffer)
