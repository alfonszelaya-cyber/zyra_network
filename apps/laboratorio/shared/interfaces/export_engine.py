"""Puerto del motor de exportacion."""
import abc
from typing import Any


class MotorExportacion(abc.ABC):
    """Contrato: convertir contenido a formatos de salida reales."""

    @abc.abstractmethod
    def exportar(self, contenido: Any, formato: str) -> bytes:
        """Produce bytes en el formato pedido; falla si no soporta."""
