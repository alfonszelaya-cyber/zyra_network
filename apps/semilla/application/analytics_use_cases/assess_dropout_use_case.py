
"""Assess Dropout Use Case (SM4). execute DENTRO
de la clase."""
from __future__ import annotations


class AssessDropoutUseCase:
    """Puente de aplicacion sobre el engine."""

    def __init__(self, dropout_engine):
        self._eng = dropout_engine

    def execute(self, *, student_id) -> dict:
        return self._eng.assess(student_id)
