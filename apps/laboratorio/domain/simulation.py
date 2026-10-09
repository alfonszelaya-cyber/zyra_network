"""Simulacion de evolucion: el escenario proyectado en el tiempo.

Produccion determinista: el motor aplica el modelo documentado
(beneficio crece, costo mejora eficiencia, riesgo sube levemente)
y produce la serie anual con el puntaje oficial LAB-CORE.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class SimulacionEvolucion(EntidadBase):
    """Resultado real de proyectar un escenario N anos."""

    prefijo_id = "sim"

    proyecto_id: Identificador = None
    escenario_id: Identificador = None
    horizonte_anios: int = 5
    crecimiento_pct: float = 0.0
    serie: list = field(default_factory=list)
    metricas: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.proyecto_id is None or self.escenario_id is None:
            raise ValueError("La simulacion requiere proyecto_id y escenario_id.")
        if not (1 <= int(self.horizonte_anios) <= 30):
            raise ValueError("horizonte_anios fuera de rango 1-30.")
        if not (-50.0 <= float(self.crecimiento_pct) <= 200.0):
            raise ValueError("crecimiento_pct fuera de rango -50 a 200.")
        self.horizonte_anios = int(self.horizonte_anios)
        self.crecimiento_pct = float(self.crecimiento_pct)

    @property
    def total_anios(self) -> int:
        return len(self.serie)
