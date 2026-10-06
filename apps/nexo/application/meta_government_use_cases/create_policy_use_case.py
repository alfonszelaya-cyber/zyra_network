
from __future__ import annotations

class CreatePolicyUseCase:
    """Crea politica y opcionalmente la activa."""

    def __init__(self, policy_engine):
        self._eng = policy_engine

    def execute(self, *, title, scope="NATIONAL",
                detail="",
                activate=False) -> dict:
        p = self._eng.create_policy(
            title=title, scope=scope,
            detail=detail)
        if activate:
            p = self._eng.activate(
                p["policy_id"])
        return p
