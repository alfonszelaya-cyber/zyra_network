"""Eventos de sistema: ciclo de vida real de LABORATORIO."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

EVENTO_ARRANCADO = "laboratorio.sistema.arrancado"
EVENTO_HEALTH = "laboratorio.sistema.health"


@dataclass(frozen=True)
class EventoSistema:
    """Evento de sistema con momento real y detalle serializable."""

    nombre: str
    detalle: dict = field(default_factory=dict)
    momento: str = ""

    @classmethod
    def crear(cls, nombre: str, detalle: dict = None) -> "EventoSistema":
        if not nombre or not str(nombre).strip():
            raise ValueError("El evento de sistema requiere nombre.")
        return cls(
            nombre=str(nombre).strip(),
            detalle=dict(detalle or {}),
            momento=datetime.now(timezone.utc).isoformat(),
        )


def evento_arrancado(app_id: str, rutas: int, motores: int) -> EventoSistema:
    """Evento de arranque con datos reales del montaje."""
    if not app_id or not str(app_id).strip():
        raise ValueError("app_id requerido para el evento de arranque.")
    return EventoSistema.crear(EVENTO_ARRANCADO, {
        "app": str(app_id),
        "rutas": int(rutas),
        "motores": int(motores),
    })


def evento_health(estado: dict) -> EventoSistema:
    """Evento con el snapshot de salud real de la app."""
    if not isinstance(estado, dict):
        raise ValueError("El evento health requiere el estado real (dict).")
    return EventoSistema.crear(EVENTO_HEALTH, {
        "ok": bool(estado.get("ok")),
        "motores_total": int(estado.get("motores_total", 0)),
        "motores_disponibles": int(estado.get("motores_disponibles", 0)),
    })
