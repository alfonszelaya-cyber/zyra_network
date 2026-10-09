"""Zona de interaccion: el eje INTERACCION del 4D.

Areas rectangulares de la escena que responden a acciones del
usuario (clic, seleccion, zona). Coordenadas dentro del lienzo.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

ACCIONES = ("clic", "seleccion", "zona", "formulario", "camara")
MAX_ZONAS_POR_ESCENA = 50


@dataclass
class ZonaInteraccion(EntidadBase):
    """Una zona interactiva de una escena."""

    prefijo_id = "int"

    escena_id: Identificador = None
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    accion: str = "clic"
    titulo: str = ""

    def __post_init__(self):
        if self.escena_id is None:
            raise ValueError("La interaccion requiere su escena.")
        for campo in ("x", "y", "w", "h"):
            valor = float(getattr(self, campo))
            if valor < 0:
                raise ValueError(campo + " no puede ser negativo.")
            setattr(self, campo, valor)
        if self.w <= 0 or self.h <= 0:
            raise ValueError("w y h deben ser positivos.")
        if self.accion not in ACCIONES:
            raise ValueError(
                "Accion invalida: " + repr(self.accion)
                + ". Validas: " + ", ".join(ACCIONES)
            )
        if not self.titulo.strip():
            raise ValueError("La interaccion requiere titulo.")
        self.titulo = self.titulo.strip()[:200]
