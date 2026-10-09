"""Puerto del motor de comprension (etapa COMPRENDER)."""
import abc
from typing import Any, Dict


class MotorComprension(abc.ABC):
    """Contrato: analizar entradas y producir hallazgos con certeza."""

    @abc.abstractmethod
    def analizar(self, entrada: Dict[str, Any]) -> Dict[str, Any]:
        """Devuelve hallazgos declarando nivel de certeza de cada uno."""
