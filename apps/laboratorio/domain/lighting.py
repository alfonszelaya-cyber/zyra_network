"""Programa de luz: el eje LUZ del 4D.

Pasos temporales (t, color, intensidad) que los motores aplican
al render. Regla de produccion: intensidad 0.0-1.0, color HEX.
"""
import re
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

PATRON_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_PASOS = 200


@dataclass
class ProgramaLuz(EntidadBase):
    """Programa temporal de iluminacion de una escena."""

    prefijo_id = "luz"

    escena_id: Identificador = None
    pasos: list = field(default_factory=list)
    ambientar_fondo: bool = False

    def __post_init__(self):
        if self.escena_id is None:
            raise ValueError("El programa de luz requiere su escena.")

    def agregar_paso(self, t: float, color: str, intensidad: float) -> dict:
        """Agrega un paso validado (tiempo creciente)."""
        t = float(t)
        if not (0.0 <= t <= 3600.0):
            raise ValueError("t fuera de rango 0-3600.")
        color = str(color).strip()
        if not PATRON_HEX.match(color):
            raise ValueError("Color de luz invalido: " + repr(color))
        intensidad = float(intensidad)
        if not (0.0 <= intensidad <= 1.0):
            raise ValueError("La intensidad debe estar entre 0.0 y 1.0.")
        if self.pasos and t <= float(self.pasos[-1]["t"]):
            raise ValueError("Los pasos deben ir en tiempo creciente.")
        if len(self.pasos) >= MAX_PASOS:
            raise ValueError("Maximo " + str(MAX_PASOS) + " pasos.")
        paso = {"t": round(t, 3), "color": color, "intensidad": round(intensidad, 3)}
        self.pasos.append(paso)
        self.marcar_actualizacion()
        return paso

    @property
    def color_dominate(self) -> str:
        """Color del paso con mayor intensidad (o blanco si vacio)."""
        if not self.pasos:
            return "#FFFFFF"
        mejor = max(self.pasos, key=lambda p: p["intensidad"])
        return mejor["color"]
