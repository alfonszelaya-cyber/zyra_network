"""Clase base de todos los motores (providers). Ley 1: nunca fingen."""
from apps.laboratorio.shared.enums.engine_status import EngineStatus


class AdaptadorMotor:
    """Estado honesto + reporte estandar para el registro de motores."""

    def __init__(self, nombre: str, tipo: str, version: str = "1.0.0"):
        if not nombre or not str(nombre).strip():
            raise ValueError("El motor requiere nombre.")
        if not tipo or not str(tipo).strip():
            raise ValueError("El motor requiere tipo.")
        self.nombre = str(nombre).strip()
        self.tipo = str(tipo).strip()
        self.version = str(version)
        self._estado = EngineStatus.NO_DISPONIBLE
        self._motivo = "Sin inicializar"

    @property
    def estado(self) -> EngineStatus:
        """Estado actual del motor."""
        return self._estado

    @property
    def motivo_estado(self) -> str:
        """Motivo declarado del estado actual."""
        return self._motivo

    def marcar_disponible(self) -> None:
        """Marca disponible solo tras verificacion real del motor."""
        self._estado = EngineStatus.DISPONIBLE
        self._motivo = ""

    def marcar_no_disponible(self, motivo: str) -> None:
        """Marca no disponible exigiendo motivo real."""
        if not motivo or not str(motivo).strip():
            raise ValueError("marcar_no_disponible exige motivo.")
        self._estado = EngineStatus.NO_DISPONIBLE
        self._motivo = str(motivo).strip()

    def capacidades(self) -> dict:
        """Cada motor real debe declarar sus capacidades."""
        raise NotImplementedError("El motor debe declarar capacidades reales.")

    def reporte(self) -> dict:
        """Reporte estandar para engine_registry."""
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "version": self.version,
            "estado": self._estado.value,
            "motivo": self._motivo,
        }
