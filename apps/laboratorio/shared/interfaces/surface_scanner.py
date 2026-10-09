"""Puerto del escaner de superficies (pipeline de proyeccion)."""
import abc
from typing import Any, Dict


class SurfaceScanner(abc.ABC):
    """Contrato del paso SCAN: capturar geometria de la superficie."""

    @abc.abstractmethod
    def disponible(self) -> bool:
        """True si hay hardware/capacidad real de escaneo."""

    @abc.abstractmethod
    def escanear(self, opciones: Dict[str, Any]) -> Dict[str, Any]:
        """Produce datos de superficie: nube de puntos o malla."""
