
"""Nexo Customer Service Engine - fachada compuesta
sobre el SupportEngine transversal (regla 69)."""
from __future__ import annotations
from apps.nexo.domain.customer_service.ticket_engine import (
    NexoTicketEngine)
from apps.nexo.domain.customer_service.escalation_engine import (
    NexoEscalationEngine)
from apps.nexo.domain.customer_service.satisfaction_engine import (
    NexoSatisfactionEngine)
from apps.nexo.domain.customer_service.support_case_engine import (
    NexoSupportCaseEngine)
from apps.nexo.domain.customer_service.service_history_engine import (
    NexoServiceHistoryEngine)

class NexoCustomerServiceEngine:
    """Fachada de atencion al cliente NEXO."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self.tickets = NexoTicketEngine(
            support_engine, app_id)
        self.escalations = NexoEscalationEngine(
            support_engine, app_id)
        self.satisfaction = NexoSatisfactionEngine(
            support_engine, app_id)
        self.cases = NexoSupportCaseEngine(
            support_engine, app_id)
        self.history = NexoServiceHistoryEngine(
            support_engine, app_id)

    def service_report(self) -> dict:
        dist = self.history.status_distribution()
        return {"report_type":
                    "NEXO_SERVICE_REPORT",
                "tickets_total":
                    sum(dist.values()),
                "status_distribution": dist,
                "open_tickets":
                    len(self.tickets.open_tickets()),
                "satisfaction":
                    self.satisfaction.average()}
