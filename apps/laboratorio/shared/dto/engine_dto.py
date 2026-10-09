"""DTO de informacion de motor para registro y UI."""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class MotorInfo:
    """Foto oficial de un motor registrado."""

    id: str
    nombre: str
    tipo: str
    estado: str
    version: str
    capacidades: Tuple[str, ...] = ()
    motivo: str = ""

    @classmethod
    def desde_reporte(cls, reporte: dict, id_motor: str) -> "MotorInfo":
        """Construye desde el reporte estandar de AdaptadorMotor."""
        for clave in ("nombre", "tipo", "estado", "version"):
            if clave not in reporte:
                raise ValueError("Reporte incompleto: falta " + clave)
        return cls(
            id=id_motor,
            nombre=reporte["nombre"],
            tipo=reporte["tipo"],
            estado=reporte["estado"],
            version=reporte["version"],
            capacidades=tuple(reporte.get("capacidades", ())),
            motivo=reporte.get("motivo", ""),
        )

    def to_dict(self) -> dict:
        """Serializacion estable."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "estado": self.estado,
            "version": self.version,
            "capacidades": list(self.capacidades),
            "motivo": self.motivo,
        }
