
"""SemillaBridge (SM6). feed_talent y
feed_certificacion via semilla_link (SE-1 intacto,
regla 69). Degradacion honesta sin link."""
from __future__ import annotations
from apps.semilla.events.contracts import make_event
from apps.semilla.infrastructure.messaging.message_bus import (
    SemillaMessageBus)

class SemillaBridge:
    """Raiz de composicion de SEMILLA en vivo."""

    def __init__(self, semilla_link=None,
                 clock=None):
        self.clock = clock
        self.link = semilla_link
        self.bus = SemillaMessageBus(clock=clock)

    def emit(self, event, student_id="",
             payload=None) -> dict:
        ev = make_event(
            event, student_id=student_id,
            payload=payload,
            occurred_at=(self.clock.now()
                         if self.clock
                         else None))
        return self.bus.publish(ev)

    def drain_events(self, limit=100) -> list:
        return self.bus.drain(limit)

    def feed_talent(self, *, student_id,
                    category, detail="") -> dict:
        r = self.emit("SEMILLA_TALENT_DETECTED",
            student_id=student_id,
            payload={"category": category,
                     "detail": detail})
        net = False
        if self.link is not None:
            try:
                self.link.record_milestone(
                    student_id, "talento",
                    category + ": " + detail)
                net = True
            except Exception:
                net = False
        return {"event": r,
                "network_history": net}

    def feed_certification(self, *, student_id,
                           title, detail="") -> dict:
        r = self.emit("SEMILLA_CERTIFIED",
            student_id=student_id,
            payload={"title": title,
                     "detail": detail})
        net = False
        if self.link is not None:
            try:
                self.link.record_milestone(
                    student_id, "certificacion",
                    title + ": " + detail)
                net = True
            except Exception:
                net = False
        return {"event": r,
                "network_history": net}

    def status(self) -> dict:
        return {"events_pending":
                    self.bus.pending(),
                "link_available":
                    self.link is not None}
