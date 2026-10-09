"""Trabajo de render: un render real de una escena en una calidad.

La imagen y su profundidad se guardan como bytes reales (BLOB).
El hash sella la imagen (integridad ZYRA) y la duracion es
medida, no estimada.
"""
from dataclasses import dataclass

from apps.laboratorio.shared.enums.render_quality import RenderQuality
from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class TrabajoRender(EntidadBase):
    """Render terminado y descargable."""

    prefijo_id = "rnd"

    proyecto_id: Identificador = None
    escena_id: Identificador = None
    calidad: RenderQuality = RenderQuality.BORRADOR
    formato: str = "svg"
    ancho: int = 0
    alto: int = 0
    imagen: bytes = b""
    profundidad: bytes = b""
    hash_sha256: str = ""
    duracion_ms: float = 0.0

    def __post_init__(self):
        if self.proyecto_id is None or self.escena_id is None:
            raise ValueError("El render requiere proyecto_id y escena_id.")
        if not isinstance(self.calidad, RenderQuality):
            raise ValueError("Calidad de render invalida.")
        if self.formato not in ("svg", "png"):
            raise ValueError("Formato de render invalido: " + repr(self.formato))
        if self.ancho < 16 or self.alto < 16:
            raise ValueError("Dimensiones del render invalidas.")
        if not self.imagen:
            raise ValueError("Un render sin imagen no es valido.")
        if self.duracion_ms < 0:
            raise ValueError("La duracion no puede ser negativa.")

    @property
    def mime(self) -> str:
        """MIME oficial del formato del render."""
        if self.formato == "svg":
            return "image/svg+xml"
        return "image/png"

    @property
    def tiene_profundidad(self) -> bool:
        """True si el canal PROFUNDIDAD fue producido."""
        return bool(self.profundidad)
