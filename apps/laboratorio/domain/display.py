"""Destino de salida registrado (Ley 1: honesto)."""
from dataclasses import dataclass

from apps.laboratorio.shared.enums.display_kind import DisplayKind
from apps.laboratorio.shared.models.base import EntidadBase

KINDS_DISPONIBLES = ("pantalla", "proyector")


@dataclass
class DestinoSalida(EntidadBase):
    """Un destino de salida registrado por un usuario."""

    prefijo_id = "dsp"

    propietario_zid: str = ""
    nombre: str = ""
    kind: DisplayKind = DisplayKind.PANTALLA

    def __post_init__(self):
        if not self.propietario_zid.strip():
            raise ValueError("La salida requiere propietario ZID.")
        if not self.nombre.strip():
            raise ValueError("La salida requiere nombre.")
        if not isinstance(self.kind, DisplayKind):
            raise ValueError("Tipo de salida invalido.")
        self.propietario_zid = self.propietario_zid.strip()
        self.nombre = self.nombre.strip()

    @property
    def disponible(self) -> bool:
        return self.kind.value in KINDS_DISPONIBLES

    @property
    def motivo_estado(self) -> str:
        if self.disponible:
            return ""
        return "hardware " + self.kind.value + " no conectado; se activara al conectarlo"
