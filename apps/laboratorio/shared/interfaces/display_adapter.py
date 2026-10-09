"""Puerto de destino de salida (Display Abstraction invertida)."""
import abc
from typing import Any, Dict


class DisplayAdapter(abc.ABC):
    """Contrato de todo destino: pantalla, proyector, holo, AR/VR."""

    @abc.abstractmethod
    def kind(self) -> str:
        """Identificador del destino."""

    @abc.abstractmethod
    def disponible(self) -> bool:
        """Ley 1: reporta honestamente si el destino esta presente."""

    @abc.abstractmethod
    def capacidades(self) -> Dict[str, Any]:
        """Resoluciones, frecuencias y modos realmente soportados."""

    @abc.abstractmethod
    def presentar(self, frame_bytes: bytes, config: Dict[str, Any]) -> Dict[str, Any]:
        """Muestra un frame y devuelve reporte real de la operacion."""
