"""Historial del proyecto: cadena de evidencia interna LAB-CORE."""

from dataclasses import dataclass, field
from typing import Dict

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class EntradaHistorial(EntidadBase):
    """Un hecho registrado: quien hizo que y con que detalle."""

    prefijo_id = "his"

    proyecto_id: Identificador = None
    autor_zid: str = ""
    accion: str = ""
    detalle: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La entrada de historial requiere proyecto_id.")
        if not self.autor_zid.strip():
            raise ValueError("La entrada de historial requiere autor ZID.")
        if not self.accion.strip():
            raise ValueError("La entrada de historial requiere accion.")
        self.autor_zid = self.autor_zid.strip()
        self.accion = self.accion.strip()
