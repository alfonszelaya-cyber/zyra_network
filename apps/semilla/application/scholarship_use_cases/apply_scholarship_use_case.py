
"""Apply Scholarship Use Case (SM3). execute DENTRO
de la clase."""
from __future__ import annotations


class ApplyScholarshipUseCase:
    """Aplica a la beca y corre la evaluacion
    automatica por criterios."""

    def __init__(self, scholarship_engine):
        self._eng = scholarship_engine

    def execute(self, *, program_id,
                student_id) -> dict:
        app = self._eng.apply(
            program_id=program_id,
            student_id=student_id)
        final = self._eng.evaluate(
            app["application_id"])
        return {"application": final}
