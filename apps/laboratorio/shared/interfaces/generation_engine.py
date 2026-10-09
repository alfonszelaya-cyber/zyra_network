"""Puerto del motor de generacion (etapa CREAR)."""
import abc
from typing import Any, Dict


class MotorGeneracion(abc.ABC):
    """Contrato: generar imagenes, video, paginas, modelos reales."""

    @abc.abstractmethod
    def generar(self, especificacion: Dict[str, Any]) -> Dict[str, Any]:
        """Genera artefactos declarando formato y bytes reales."""
