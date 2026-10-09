"""Puerto del motor de render.

Regla 4D: todo render de produccion entrega COLOR y PROFUNDIDAD.
La profundidad alimenta multi-plano, light-field y holografia.
"""
import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ResultadoRender:
    """Salida de un render: color obligatorio, profundidad exigida."""

    imagen_bytes: bytes
    profundidad_bytes: Optional[bytes]
    ancho: int
    alto: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tiene_profundidad(self) -> bool:
        """True si el canal PROFUNDIDAD fue producido."""
        return self.profundidad_bytes is not None and len(self.profundidad_bytes) > 0


class Renderer(abc.ABC):
    """Contrato que todo motor de render debe cumplir."""

    @abc.abstractmethod
    def renderizar(self, escena: Any, opciones: Dict[str, Any]) -> ResultadoRender:
        """Renderiza una escena con calidad y resolucion en opciones."""

    @abc.abstractmethod
    def capacidades(self) -> Dict[str, Any]:
        """Declara calidades y formatos realmente soportados."""
