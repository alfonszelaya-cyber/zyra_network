"""Puerto del motor de simulacion (etapa SIMULAR)."""
import abc
from typing import Any, Dict

from apps.laboratorio.domain.scenario import Escenario


class MotorSimulacion(abc.ABC):
    """Contrato: ejecutar escenarios A/B/C y devolver metricas reales."""

    @abc.abstractmethod
    def ejecutar(self, escenario: Escenario, horizonte: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el escenario dentro del horizonte temporal dado."""
