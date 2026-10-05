
from __future__ import annotations
from apps.nexo.domain.executive.executive_decision_engine import ExecutiveDecisionEngine

class SupportDecisionUseCase:
    def __init__(self, decision_engine):
        self._engine = decision_engine

    def execute(self, *, decision_context,
                recommendation="REVIEW_REQUIRED", priority="NORMAL"):
        return self._engine.support_decision(
            decision_context=decision_context,
            recommendation=recommendation, priority=priority)
