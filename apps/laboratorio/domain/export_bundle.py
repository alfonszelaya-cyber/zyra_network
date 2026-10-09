"""Exportacion: bundle verificable del proyecto (ZIP + manifiesto).

El manifiesto lista cada pieza con su hash SHA-256 real; el ZIP
se produce con stdlib zipfile. El envio a otra app ZYRA pasa por
el outbox existente.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

TIPOS_EXPORT = ("bundle_verificable", "envio_zyra")
DESTINOS_ZYRA = (
    "nexo", "agro", "semilla", "mpe", "axis", "subastas",
    "ciclo", "govdata", "superapp",
)


@dataclass
class Exportacion(EntidadBase):
    """Exportacion terminada del proyecto."""

    prefijo_id = "exp"

    proyecto_id: Identificador = None
    tipo: str = "bundle_verificable"
    destino: str = ""
    piezas: list = field(default_factory=list)
    tamano_total: int = 0
    hash_sha256: str = ""

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La exportacion requiere su proyecto.")
        if self.tipo not in TIPOS_EXPORT:
            raise ValueError(
                "Tipo de exportacion invalido: " + repr(self.tipo)
                + ". Validos: " + ", ".join(TIPOS_EXPORT)
            )
        if self.tipo == "envio_zyra":
            destino = str(self.destino or "").strip().lower()
            if destino not in DESTINOS_ZYRA:
                raise ValueError(
                    "Destino ZYRA invalido: " + repr(self.destino)
                    + ". Validos: " + ", ".join(DESTINOS_ZYRA)
                )
            self.destino = destino
        if not self.piezas:
            raise ValueError("Una exportacion sin piezas no es valida.")

    @property
    def es_envio(self) -> bool:
        return self.tipo == "envio_zyra"
