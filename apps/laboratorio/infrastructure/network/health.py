"""Estado de salud real de LABORATORIO (sin fingir nada)."""
from datetime import datetime, timezone

from apps.laboratorio.constants.system.system_constants import SistemaConstantes


class EstadoSalud:
    """Consulta BD, motores y configuracion de red reales."""

    def __init__(self, conexion, config_red, registro_motores):
        self._cx = conexion
        self._cfg_red = config_red
        self._motores = registro_motores

    def estado(self) -> dict:
        try:
            self._cx.consultar("SELECT 1")
            bd = True
        except Exception:
            bd = False
        motores = self._motores.reporte_todos()
        disponibles = sum(1 for m in motores if m.get("estado") == "disponible")
        return {
            "ok": bd,
            "app": SistemaConstantes.ID_APP,
            "version": SistemaConstantes.VERSION_APP,
            "base_datos": bd,
            "motores_total": len(motores),
            "motores_disponibles": disponibles,
            "red_configurada": self._cfg_red.configurada,
            "momento": datetime.now(timezone.utc).isoformat(),
        }
