"""Presentacion espacial: pasos reales sobre escenas del proyecto.

Cada paso ancla una escena real (validada), con duracion,
transicion y texto de narracion. El sello conecta con ZYRA via
el outbox existente (nada se duplica).
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

TRANSICIONES = ("corte", "desvanecer", "deslizar", "zoom")
MAX_PASOS = 60
MIN_DURACION = 1.0
MAX_DURACION = 300.0


@dataclass
class Presentacion(EntidadBase):
    """Presentacion estructurada de un proyecto."""

    prefijo_id = "prs"

    proyecto_id: Identificador = None
    titulo: str = ""
    pasos: list = field(default_factory=list)
    sellada: bool = False
    sello_zid: str = ""
    duracion_total: float = 0.0

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La presentacion requiere su proyecto.")
        if not self.titulo.strip():
            raise ValueError("La presentacion requiere titulo.")
        self.titulo = self.titulo.strip()

    def agregar_paso(self, escena_id, duracion: float, transicion: str, narracion: str = "") -> dict:
        """Agrega un paso validado con escena real."""
        escena_texto = str(escena_id).strip()
        if not escena_texto:
            raise ValueError("El paso requiere la escena del proyecto.")
        duracion = float(duracion)
        if not (MIN_DURACION <= duracion <= MAX_DURACION):
            raise ValueError(
                "duracion fuera de rango 1-300: " + str(duracion)
            )
        transicion = str(transicion).strip().lower()
        if transicion not in TRANSICIONES:
            raise ValueError(
                "Transicion invalida: " + repr(transicion)
                + ". Validas: " + ", ".join(TRANSICIONES)
            )
        if len(self.pasos) >= MAX_PASOS:
            raise ValueError("Maximo " + str(MAX_PASOS) + " pasos.")
        if self.sellada:
            raise ValueError("La presentacion ya esta sellada: no se puede modificar.")
        paso = {
            "escena_id": escena_texto,
            "duracion_s": round(duracion, 3),
            "transicion": transicion,
            "narracion": str(narracion or "").strip()[:300],
        }
        self.pasos.append(paso)
        self.duracion_total = round(
            sum(p["duracion_s"] for p in self.pasos), 3
        )
        self.marcar_actualizacion()
        return paso

    def marcar_sellada(self, zid: str) -> None:
        """Sella la presentacion con el ZID del actor."""
        if self.sellada:
            raise ValueError("La presentacion ya esta sellada.")
        if not zid or not str(zid).strip():
            raise ValueError("Sellar exige el ZID del actor.")
        self.sellada = True
        self.sello_zid = str(zid).strip()
        self.marcar_actualizacion()
