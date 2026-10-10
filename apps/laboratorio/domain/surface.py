"""Superficie proyectable: pared, piso, fachada, maqueta."""
from dataclasses import dataclass, field

from apps.laboratorio.shared.enums.surface_kind import SurfaceKind
from apps.laboratorio.shared.models.base import EntidadBase

MAX_COORD = 100000


@dataclass
class Superficie(EntidadBase):
    """Una superficie fisica donde se puede proyectar."""

    prefijo_id = "sup"

    propietario_zid: str = ""
    nombre: str = ""
    tipo: SurfaceKind = SurfaceKind.PARED
    corners: list = field(default_factory=list)
    homografia: list = field(default_factory=list)
    calibrada: bool = False

    def __post_init__(self):
        if not self.propietario_zid.strip():
            raise ValueError("La superficie requiere propietario ZID.")
        if not self.nombre.strip():
            raise ValueError("La superficie requiere nombre.")
        if not isinstance(self.tipo, SurfaceKind):
            raise ValueError("Tipo de superficie invalido.")
        self.propietario_zid = self.propietario_zid.strip()
        self.nombre = self.nombre.strip()

    def definir_corners(self, corners) -> list:
        """Valida y guarda las 4 esquinas del cuadrilatero."""
        if self.calibrada:
            raise ValueError("La superficie ya esta calibrada.")
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError("Se requieren exactamente 4 esquinas.")
        limpias = []
        for punto in corners:
            if not isinstance(punto, (list, tuple)) or len(punto) != 2:
                raise ValueError("Cada esquina debe ser [x, y].")
            x, y = float(punto[0]), float(punto[1])
            if not (0.0 <= x <= MAX_COORD and 0.0 <= y <= MAX_COORD):
                raise ValueError("Esquina fuera de rango 0-100000.")
            limpias.append([round(x, 3), round(y, 3)])
        self.corners = limpias
        self.marcar_actualizacion()
        return self.corners

    def marcar_calibrada(self, homografia) -> None:
        if not isinstance(homografia, list) or len(homografia) != 9:
            raise ValueError("La homografia debe tener 9 valores.")
        valores = []
        for v in homografia:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("La homografia debe ser numerica.")
            valores.append(round(float(v), 8))
        self.homografia = valores
        self.calibrada = True
        self.marcar_actualizacion()
