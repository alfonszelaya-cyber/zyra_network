"""Artefacto: entregable generado desde una escena.

Todo artefacto guarda su contenido real, su hash SHA-256 y su
formato. Ningun artefacto finge: si el formato no existe, no se
genera (video_mp4 llega en fase 6 con el motor de secuencia).
"""
from dataclasses import dataclass

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

FORMATOS_GENERACION = ("imagen", "pagina", "modelo", "animacion")
MIME_POR_FORMATO = {
    "imagen": "image/svg+xml",
    "pagina": "text/html; charset=utf-8",
    "modelo": "application/json",
    "animacion": "image/svg+xml",
}


@dataclass
class Artefacto(EntidadBase):
    """Salida real y descargable de una escena."""

    prefijo_id = "art"

    proyecto_id: Identificador = None
    escena_id: Identificador = None
    nombre: str = ""
    formato: str = ""
    contenido: str = ""
    hash_sha256: str = ""
    tamano_bytes: int = 0

    def __post_init__(self):
        if self.proyecto_id is None or self.escena_id is None:
            raise ValueError("El artefacto requiere proyecto_id y escena_id.")
        if not self.nombre.strip():
            raise ValueError("El artefacto requiere nombre.")
        self.nombre = self.nombre.strip()
        if self.formato not in FORMATOS_GENERACION:
            raise ValueError(
                "Formato de generacion invalido: " + repr(self.formato)
                + ". Validos: " + ", ".join(FORMATOS_GENERACION)
            )

    @property
    def mime(self) -> str:
        """MIME oficial del formato del artefacto."""
        return MIME_POR_FORMATO[self.formato]
