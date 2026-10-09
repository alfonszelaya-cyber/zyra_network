"""Manifiesto oficial de un modulo vertical."""
import re
from dataclasses import dataclass

PATRON_ID = re.compile(r"^[a-z][a-z0-9_]{2,30}$")


@dataclass(frozen=True)
class ManifiestoModulo:
    id: str
    nombre: str
    version: str = "1.0.0"
    descripcion: str = ""

    def __post_init__(self):
        if not PATRON_ID.match(self.id or ""):
            raise ValueError("Id de modulo invalido: " + repr(self.id))
        if not self.nombre or not self.nombre.strip():
            raise ValueError("El modulo requiere nombre.")
        if not self.version or not self.version.strip():
            raise ValueError("El modulo requiere version.")
