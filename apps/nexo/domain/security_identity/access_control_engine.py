
"""Nexo Access Control Engine - decisiones de acceso
(NG8). Accion -> rol -> decision."""
from __future__ import annotations

ACTION_ROLE = {"READ": "VIEWER",
               "OPERATE": "OPERATOR",
               "APPROVE": "APPROVER",
               "ADMIN": "ADMIN"}

class NexoAccessControlEngine:
    """Decisiones allow/deny con razon."""

    def __init__(self, authorization_engine):
        self._authz = authorization_engine

    def decide(self, *, actor, company_id,
               action, amount="0") -> dict:
        role = ACTION_ROLE.get(action)
        if role is None:
            return {"allowed": False,
                    "reason": "accion desconocida: "
                              + str(action)}
        r = self._authz.can(
            actor=actor, company_id=company_id,
            role_needed=role, amount=amount)
        return {"action": action,
                "actor": actor,
                "company_id": company_id,
                "allowed": r["allowed"],
                "reason": r["reason"]}
