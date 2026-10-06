
"""Contratos de eventos NEXO_* (catalogo oficial).

Fuente unica de nombres de eventos NEXO_* del dominio.
Todo evento tiene: event_id, event, source, version,
company_id, payload, occurred_at. Solo eventos del
catalogo pueden emitirse (produccion real, sin improvisar)."""
from __future__ import annotations
import uuid

SOURCE = "nexo"
EVENT_VERSION = "1.0"

NEXO_COMPANY_REGISTERED = "NEXO_COMPANY_REGISTERED"
NEXO_OPERATION_CREATED = "NEXO_OPERATION_CREATED"
NEXO_OPERATION_COMPLETED = "NEXO_OPERATION_COMPLETED"
NEXO_JOURNAL_POSTED = "NEXO_JOURNAL_POSTED"
NEXO_INVOICE_POSTED = "NEXO_INVOICE_POSTED"
NEXO_PAYMENT_RECEIVED = "NEXO_PAYMENT_RECEIVED"
NEXO_PAYMENT_SENT = "NEXO_PAYMENT_SENT"
NEXO_TAX_DECLARED = "NEXO_TAX_DECLARED"
NEXO_PERIOD_CLOSED = "NEXO_PERIOD_CLOSED"
NEXO_DOCUMENT_SEALED = "NEXO_DOCUMENT_SEALED"
NEXO_AUDIT_APPENDED = "NEXO_AUDIT_APPENDED"

NEXO_EVENTS = (
    NEXO_COMPANY_REGISTERED, NEXO_OPERATION_CREATED,
    NEXO_OPERATION_COMPLETED, NEXO_JOURNAL_POSTED,
    NEXO_INVOICE_POSTED, NEXO_PAYMENT_RECEIVED,
    NEXO_PAYMENT_SENT, NEXO_TAX_DECLARED,
    NEXO_PERIOD_CLOSED, NEXO_DOCUMENT_SEALED,
    NEXO_AUDIT_APPENDED)

def is_valid_event(name) -> bool:
    return name in NEXO_EVENTS

def make_event(name, company_id="", payload=None,
               occurred_at=None) -> dict:
    if not is_valid_event(name):
        raise ValueError("evento no catalogado: " + str(name))
    return {"event_id": "NEXOEVT-" + str(uuid.uuid4()),
            "event": name, "source": SOURCE,
            "version": EVENT_VERSION,
            "company_id": str(company_id),
            "payload": dict(payload or {}),
            "occurred_at": occurred_at}
