"""Comparacion: decision fundamentada entre escenarios evaluados.

El ganador se declara con datos: participantes ordenados por el
puntaje oficial, brecha contra el segundo y desglose por
dimension (costo, beneficio, riesgo). Incluye informe HTML.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class Comparacion(EntidadBase):
    """Resultado real de comparar los escenarios de un proyecto."""

    prefijo_id = "cmp"

    proyecto_id: Identificador = None
    participantes: list = field(default_factory=list)
    ganador: str = ""
    brecha: float = 0.0
    detalle: dict = field(default_factory=dict)
    informe: str = ""

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La comparacion requiere su proyecto.")
        if not self.ganador.strip():
            raise ValueError("La comparacion requiere ganador.")
        if len(self.participantes) < 2:
            raise ValueError("La comparacion requiere al menos 2 participantes.")
        self.ganador = self.ganador.strip()
        self.informe = str(self.informe)[:100000]
