"""Activo de biblioteca: material reutilizable sellado con SHA-256."""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase

TIPOS_ACTIVO = ("svg", "html", "json", "texto", "imagen")
MAX_ETIQUETAS = 10


@dataclass
class Activo(EntidadBase):
    """Activo guardado en la biblioteca del usuario."""

    prefijo_id = "ast"

    propietario_zid: str = ""
    nombre: str = ""
    tipo: str = ""
    contenido: str = ""
    hash_sha256: str = ""
    tamano_bytes: int = 0
    etiquetas: list = field(default_factory=list)

    def __post_init__(self):
        if not self.propietario_zid.strip():
            raise ValueError("El activo requiere propietario ZID.")
        if not self.nombre.strip():
            raise ValueError("El activo requiere nombre.")
        if self.tipo not in TIPOS_ACTIVO:
            raise ValueError(
                "Tipo de activo invalido: " + repr(self.tipo)
                + ". Validos: " + ", ".join(TIPOS_ACTIVO)
            )
        self.propietario_zid = self.propietario_zid.strip()
        self.nombre = self.nombre.strip()
        if len(self.etiquetas) > MAX_ETIQUETAS:
            raise ValueError("Maximo " + str(MAX_ETIQUETAS) + " etiquetas por activo.")
        self.etiquetas = [str(e).strip().lower()[:40] for e in self.etiquetas if str(e).strip()]

    def tiene_etiqueta(self, etiqueta: str) -> bool:
        """True si el activo lleva la etiqueta pedida."""
        return str(etiqueta).strip().lower() in self.etiquetas
