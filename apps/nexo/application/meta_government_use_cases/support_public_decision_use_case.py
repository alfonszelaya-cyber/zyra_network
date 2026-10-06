
from __future__ import annotations

class SupportPublicDecisionUseCase:
    """Soporte de decision: propuesta + analisis +
    decision entre opciones (nivel 5)."""

    def __init__(self, decisions):
        self._eng = decisions

    def execute(self, *, title, options,
                analysis="", chosen=None) -> dict:
        d = self._eng.propose_decision(
            title=title, options=options)
        if analysis:
            d = self._eng.record_analysis(
                decision_id=d["decision_id"],
                analysis=analysis)
        if chosen:
            d = self._eng.decide(
                decision_id=d["decision_id"],
                chosen=chosen)
        return d
