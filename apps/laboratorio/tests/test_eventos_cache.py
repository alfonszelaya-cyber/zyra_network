"""Feed de eventos, cache TTL y notificaciones."""
import time

from apps.laboratorio.infrastructure.cache import CacheTTL
from apps.laboratorio.infrastructure.messaging.event_bus import BusEventos
from apps.laboratorio.registry.services.service_registry import ColectorEventos
from apps.laboratorio.shared.interfaces.event_bus import Evento
from apps.laboratorio.events.system import evento_arrancado
from apps.laboratorio.events.notifications import Notificador


def test_feed_captura_eventos_del_bus():
    bus = BusEventos()
    colector = ColectorEventos()
    colector.conectar(bus)
    bus.publicar(Evento(nombre="laboratorio.test.feed", datos={"n": 1}))
    bus.publicar(Evento(nombre="laboratorio.test.feed", datos={"n": 2}))
    feed = colector.historial(0, 10)
    assert feed["devueltos"] == 2
    cursor = feed["cursor_sugerido"]
    assert colector.historial(cursor, 10)["devueltos"] == 0


def test_cache_ttl_expira_real():
    cache = CacheTTL(ttl_segundos=0.1, maxlen=10)
    cache.poner("k", "v")
    assert cache.obtener("k") == "v"
    time.sleep(0.15)
    assert cache.obtener("k") is None
    assert cache.estadisticas()["expiraciones"] >= 1


def test_notificador_registra_eventos_de_sistema():
    notificador = Notificador()
    registro = notificador.notificar(
        evento_arrancado("laboratorio", 74, 17), "arranque"
    )
    assert registro["canal"] == "memoria"
    assert notificador.historial(0, 5)["devueltas"] == 1
