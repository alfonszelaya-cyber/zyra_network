"""Consultas de escenarios y evaluaciones."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsultaListarEscenarios:
    proyecto_id: str


@dataclass(frozen=True)
class ConsultaEvaluaciones:
    escenario_id: str
