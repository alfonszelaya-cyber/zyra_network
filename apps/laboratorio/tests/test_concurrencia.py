"""Concurrencia real: escrituras simultaneas sin corrupcion."""
import json
import threading

from apps.laboratorio.infrastructure.api.app import montar_aplicacion
from apps.laboratorio.infrastructure.cache import CacheTTL
from apps.laboratorio.infrastructure.messaging.event_bus import BusEventos
from apps.laboratorio.shared.interfaces.event_bus import Evento
from apps.laboratorio.tests.conftest import IDENTIDAD_HEADERS, assert_2xx


def test_10_hilos_crea_proyectos_simultaneos():
    app = montar_aplicacion(":memory:")
    resultados = []
    errores = []
    lock = threading.Lock()

    def _crear(indice):
        try:
            salida = app.despachar(
                "POST", "/laboratorio/api/v1/projects",
                dict(IDENTIDAD_HEADERS),
                json.dumps({"titulo": "Hilo " + str(indice), "tipo": "negocio"}).encode("utf-8"),
            )
            with lock:
                resultados.append(salida[0])
        except Exception as exc:
            with lock:
                errores.append(str(exc))

    hilos = [threading.Thread(target=_crear, args=(i,)) for i in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert not errores, errores
    assert len(resultados) == 10
    assert all(200 <= c < 300 for c in resultados), resultados


def test_bus_aisla_fallos_y_no_pierde_eventos():
    bus = BusEventos()
    recibidos = []
    bus.suscribir("ev.x", lambda e: recibidos.append(e))

    def _fallador(_e):
        raise RuntimeError("intencional")

    bus.suscribir("ev.x", _fallador)
    for i in range(20):
        bus.publicar(Evento(nombre="ev.x", datos={"i": i}))
    assert len(recibidos) == 20


def test_cache_ttl_concurrente_sin_excepciones():
    cache = CacheTTL(ttl_segundos=5.0, maxlen=100)

    def _escribir(indice):
        for i in range(50):
            cache.poner("k" + str(indice) + "-" + str(i), i)
            cache.obtener("k" + str(indice) + "-" + str(i))

    hilos = [threading.Thread(target=_escribir, args=(i,)) for i in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert cache.estadisticas()["entradas"] <= 100
