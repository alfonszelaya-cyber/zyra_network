"""DTO de estado de proyeccion en vivo."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EstadoProyeccion:
    """Estado real de una sesion de proyeccion (sin fingir exito)."""

    activa: bool
    superficie_id: str
    destino: str
    fps: float
    mensaje: str = ""

    @classmethod
    def detener(cls, superficie_id: str, motivo: str = "") -> "EstadoProyeccion":
        """Estado detenido con motivo honesto."""
        return cls(False, superficie_id, "", 0.0, motivo or "detenida")

    def to_dict(self) -> dict:
        """Serializacion estable."""
        return {
            "activa": self.activa,
            "superficie_id": self.superficie_id,
            "destino": self.destino,
            "fps": self.fps,
            "mensaje": self.mensaje,
        }
