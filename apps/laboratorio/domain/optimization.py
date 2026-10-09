"""Propuesta de optimizacion: mejoras concretas y verificables.

El motor sugiere acciones por regla (costo, riesgo, beneficio),
calcula los parametros optimizados y el puntaje proyectado con
la formula oficial. Al aplicar, nace un escenario real nuevo.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

ESTADO_SUGERIDA = "sugerida"
ESTADO_APLICADA = "aplicada"


@dataclass
class PropuestaOptimizacion(EntidadBase):
    """Mejoras sugeridas para un escenario, aplicables como nuevo."""

    prefijo_id = "opt"

    proyecto_id: Identificador = None
    escenario_id: Identificador = None
    recomendaciones: list = field(default_factory=list)
    parametros_optimizados: dict = field(default_factory=dict)
    puntaje_actual: float = 0.0
    puntaje_proyectado: float = 0.0
    estado: str = ESTADO_SUGERIDA
    aplicado_como: str = ""

    def __post_init__(self):
        if self.proyecto_id is None or self.escenario_id is None:
            raise ValueError("La propuesta requiere proyecto_id y escenario_id.")
        if not self.recomendaciones:
            raise ValueError("La propuesta requiere al menos una recomendacion.")
        if self.estado not in (ESTADO_SUGERIDA, ESTADO_APLICADA):
            raise ValueError("Estado de propuesta invalido: " + repr(self.estado))
        for clave, valor in self.parametros_optimizados.items():
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError("Parametro optimizado no numerico: " + clave)

    def marcar_aplicada(self, escenario_nuevo_id: str) -> None:
        """Marca la propuesta como aplicada con su escenario real."""
        if not escenario_nuevo_id or not str(escenario_nuevo_id).strip():
            raise ValueError("marcar_aplicada exige el id del escenario creado.")
        if self.estado == ESTADO_APLICADA:
            raise ValueError("La propuesta ya fue aplicada.")
        self.estado = ESTADO_APLICADA
        self.aplicado_como = str(escenario_nuevo_id).strip()
        self.marcar_actualizacion()

    @property
    def mejora_estimada(self) -> float:
        """Cuanto mejora el puntaje si se aplica la propuesta."""
        return round(self.puntaje_proyectado - self.puntaje_actual, 4)
