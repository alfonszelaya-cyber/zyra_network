"""Estado de salud real de LABORATORIO (sin fingir nada).

Reporta base de datos real, los motores reales registrados y el
estado VERDADERO del enlace con ZYRA Core (configurada/conectada).
"""
from datetime import datetime, timezone

from apps.laboratorio.constants.system.system_constants import SistemaConstantes


class EstadoSalud:
    """Consulta BD, motores, cliente de red y configuracion reales."""

    def __init__(self, conexion, config_red, registro_motores, cliente_zyra=None):
        self._cx = conexion
        self._cfg_red = config_red
        self._motores = registro_motores
        self._cliente = cliente_zyra

    def estado(self) -> dict:
        try:
            self._cx.consultar("SELECT 1")
            bd = True
        except Exception:
            bd = False
        motores = self._motores.reporte_todos()
        disponibles = sum(
            1 for m in motores if m.get("estado") == "disponible"
        )
        if self._cliente is not None:
            red = dict(self._cliente.estado_conexion())
        else:
            red = {
                "configurada": bool(
                    getattr(self._cfg_red, "configurada", False)
                ),
                "conectada": False,
                "motivo": "sin cliente de red montado",
            }
        return {
            "ok": bd,
            "app": SistemaConstantes.ID_APP,
            "version": SistemaConstantes.VERSION_APP,
            "base_datos": bd,
            "motores_total": len(motores),
            "motores_disponibles": disponibles,
            "motores_no_disponibles": len(motores) - disponibles,
            "red": red,
            "momento": datetime.now(timezone.utc).isoformat(),
        }
