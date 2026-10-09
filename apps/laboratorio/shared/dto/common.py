"""Respuesta estandar de la capa de aplicacion."""
from dataclasses import dataclass, field

from apps.laboratorio.shared.types.json_type import ObjetoJSON


@dataclass(frozen=True)
class Respuesta:
    """Sobre comun: ok + datos o ok=False + error tipificado."""

    ok: bool
    datos: ObjetoJSON = field(default_factory=dict)
    error: ObjetoJSON = field(default_factory=dict)

    @classmethod
    def exito(cls, datos: ObjetoJSON = None) -> "Respuesta":
        """Respuesta de exito con datos."""
        return cls(True, dict(datos or {}), {})

    @classmethod
    def fallo(cls, codigo: str, mensaje: str) -> "Respuesta":
        """Respuesta de fallo tipificada."""
        if not codigo or not mensaje:
            raise ValueError("fallo requiere codigo y mensaje.")
        return cls(False, {}, {"codigo": codigo, "mensaje": mensaje})

    def to_dict(self) -> ObjetoJSON:
        """Serializacion estable para API y logs."""
        return {"ok": self.ok, "datos": self.datos, "error": self.error}
