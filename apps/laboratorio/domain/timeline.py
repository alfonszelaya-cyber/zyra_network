"""Linea de tiempo: el eje TIEMPO del 4D.

Una linea por escena con pistas y keyframes validados. Los
keyframes van en segundos crecientes; el motor de render los
consume para animar objetos reales.
"""
from dataclasses import dataclass, field

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

PROPIEDADES = ("posicion", "rotacion", "escala", "visibilidad", "opacidad", "color")
MAX_DURACION = 3600.0
MAX_KEYFRAMES = 500


@dataclass
class LineaTiempo(EntidadBase):
    """Eje temporal de una escena."""

    prefijo_id = "tln"

    escena_id: Identificador = None
    duracion_s: float = 10.0
    fps: int = 30
    pistas: list = field(default_factory=list)

    def __post_init__(self):
        if self.escena_id is None:
            raise ValueError("La linea de tiempo requiere su escena.")
        if not (0.1 <= float(self.duracion_s) <= MAX_DURACION):
            raise ValueError("duracion_s fuera de rango 0.1-3600.")
        if not (1 <= int(self.fps) <= 120):
            raise ValueError("fps fuera de rango 1-120.")
        self.duracion_s = float(self.duracion_s)
        self.fps = int(self.fps)

    def agregar_pista(self, objetivo: str, propiedad: str, keyframes: list) -> dict:
        """Agrega una pista con keyframes validados."""
        if not objetivo or not str(objetivo).strip():
            raise ValueError("La pista requiere objetivo.")
        if propiedad not in PROPIEDADES:
            raise ValueError(
                "Propiedad invalida: " + repr(propiedad)
                + ". Validas: " + ", ".join(PROPIEDADES)
            )
        if not isinstance(keyframes, list) or not keyframes:
            raise ValueError("La pista requiere al menos un keyframe.")
        limpios = []
        previo = -1.0
        for kf in keyframes:
            if not isinstance(kf, dict):
                raise ValueError("Cada keyframe debe ser un objeto.")
            t = float(kf.get("t", -1))
            if not (0.0 <= t <= self.duracion_s):
                raise ValueError(
                    "Keyframe t fuera de la duracion: " + str(t)
                )
            if t <= previo:
                raise ValueError("Los keyframes deben ir en tiempo creciente.")
            previo = t
            valor = kf.get("valor", "")
            if isinstance(valor, (dict, list)):
                raise ValueError("El valor del keyframe debe ser escalar o texto.")
            limpios.append({"t": round(t, 3), "valor": str(valor)[:100]})
        if len(limpios) > MAX_KEYFRAMES:
            raise ValueError("Maximo " + str(MAX_KEYFRAMES) + " keyframes por pista.")
        pista = {
            "objetivo": str(objetivo).strip()[:120],
            "propiedad": propiedad,
            "keyframes": limpios,
        }
        self.pistas.append(pista)
        self.marcar_actualizacion()
        return pista

    @property
    def total_keyframes(self) -> int:
        return sum(len(p["keyframes"]) for p in self.pistas)
