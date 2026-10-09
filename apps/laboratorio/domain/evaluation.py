"""Evaluacion persistible: resultado de evaluate_scenario()."""

from dataclasses import dataclass, field
from typing import Dict

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class Evaluacion(EntidadBase):
    """Guarda el resultado de evaluar un escenario en un momento."""

    prefijo_id = "eva"

    escenario_id: Identificador = None
    proyecto_id: Identificador = None
    metricas: Dict[str, object] = field(default_factory=dict)
    nota: str = ""

    def __post_init__(self):
        if self.escenario_id is None or self.proyecto_id is None:
            raise ValueError(
                "La evaluacion requiere escenario_id y proyecto_id."
            )

    @property
    def puntaje_total(self) -> float:
        """Puntaje total guardado en las metricas."""
        valor = self.metricas.get("puntaje_total", 0.0)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
        return 0.0
