"""Notificaciones: canal real de eventos hacia el operador.

Registro en memoria (circular) + via logging. Sin fingir envios:
cada notificacion declara el canal por el que realmente salio.
"""
import logging
import threading
from collections import deque

from apps.laboratorio.events.system import EventoSistema

CANAL_LOG = "log"
CANAL_MEMORIA = "memoria"
MAX_NOTIFICACIONES = 500


class Notificador:
    """Registra notificaciones reales en memoria y en el log."""

    def __init__(self, maxlen: int = MAX_NOTIFICACIONES):
        if int(maxlen) < 1:
            raise ValueError("maxlen debe ser mayor o igual a 1.")
        self._historial = deque(maxlen=int(maxlen))
        self._lock = threading.Lock()
        self._logger = logging.getLogger("laboratorio.notificaciones")
        self._contador = 0

    def notificar(self, evento: EventoSistema, mensaje: str = "") -> dict:
        if not isinstance(evento, EventoSistema):
            raise ValueError("notificar requiere un EventoSistema.")
        texto = str(mensaje or "").strip() or evento.nombre
        with self._lock:
            self._contador += 1
            registro = {
                "id": "notif-" + str(self._contador).zfill(6),
                "evento": evento.nombre,
                "mensaje": texto[:300],
                "momento": evento.momento,
                "canal": CANAL_MEMORIA,
                "detalle": dict(evento.detalle),
            }
            self._historial.append(registro)
        self._logger.info(
            "[laboratorio] " + evento.nombre + ": " + texto
        )
        return dict(registro)

    def historial(self, desde: int = 0, limite: int = 50) -> dict:
        if int(desde) < 0:
            raise ValueError("desde no puede ser negativo.")
        if int(limite) < 1 or int(limite) > 500:
            raise ValueError("limite debe estar entre 1 y 500.")
        with self._lock:
            todos = list(self._historial)
        seleccion = [
            n for n in todos
            if int(n["id"].split("-")[1]) > int(desde)
        ]
        return {
            "total": len(todos),
            "devueltas": len(seleccion[: int(limite)]),
            "notificaciones": seleccion[: int(limite)],
            "canales": (CANAL_MEMORIA, CANAL_LOG),
        }
