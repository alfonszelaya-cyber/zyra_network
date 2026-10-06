
"""NexoRuntime - raiz de composicion de NEXO en
vivo (NG12). Regla 69: cero duplicar."""
from __future__ import annotations
from apps.nexo.infrastructure.messaging.message_bus import (
    NexoMessageBus)
from apps.nexo.services.transversal.currency.currency_gateway import (
    NexoCurrencyGateway)
from apps.nexo.services.transversal.ai.ai_gateway import (
    NexoAIGateway)
from apps.nexo.services.transversal.audit.audit_gateway import (
    NexoAuditGateway)

class NexoRuntime:
    """Runtime de produccion de NEXO."""

    def __init__(self, db=None, clock=None,
                 outbox=None, ai_chain=None):
        self.clock = clock
        self.bus = NexoMessageBus(outbox=outbox,
                                  clock=clock)
        self.currency = NexoCurrencyGateway()
        self.ai = NexoAIGateway(chain=ai_chain)
        self.audit = NexoAuditGateway(db=db,
                                      clock=clock)

    def emit(self, event, company_id="",
             payload=None) -> dict:
        from apps.nexo.events.contracts import (
            make_event)
        ev = make_event(
            event, company_id=company_id,
            payload=payload,
            occurred_at=(self.clock.now()
                         if self.clock
                         else None))
        return self.bus.publish(ev)

    def drain_events(self, limit=100) -> list:
        return self.bus.drain(limit)

    def classify_document(self, text) -> dict:
        return self.ai.classify_document(text)

    def audit_event(self, *, event, actor="",
                    entity="", before=None,
                    after=None) -> dict:
        return self.audit.record_event(
            event=event, actor=actor,
            entity=entity, before=before,
            after=after)

    def convert(self, amount, base,
                quote) -> dict:
        return self.currency.convert(
            amount, base, quote)

    def status(self) -> dict:
        return {"events_pending":
                    self.bus.pending(),
                "currency_mode":
                    self.currency.mode,
                "ai_mode": self.ai.mode,
                "audit_mode": self.audit.mode}
