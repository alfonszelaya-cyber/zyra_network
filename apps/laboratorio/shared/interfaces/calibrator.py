"""Puerto de calibracion proyector-superficie."""
import abc
from typing import Any, Dict


class Calibrador(abc.ABC):
    """Contrato de los pasos CALIBRACION + PIXEL MAP + WARP."""

    @abc.abstractmethod
    def calibrar(self, datos_superficie: Dict[str, Any], config_proyector: Dict[str, Any]) -> Dict[str, Any]:
        """Devuelve parametros reales de warp, mezcla y color."""
