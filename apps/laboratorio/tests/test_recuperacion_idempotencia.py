"""Recuperacion tras fallos + idempotencia real."""
import json
import os
import tempfile

from apps.laboratorio.infrastructure.api.app import montar_aplicacion
from apps.laboratorio.shared.decorators.idempotent import idempotente
from apps.laboratorio.tests.conftest import IDENTIDAD_HEADERS, assert_2xx


def test_evaluar_con_red_caida_deja_pendiente_en_outbox(app):
    salida = app.despachar(
        "POST", "/laboratorio/api/v1/projects",
        dict(IDENTIDAD_HEADERS),
        json.dumps({"titulo": "Red caida", "tipo": "negocio"}).encode("utf-8"),
    )
    assert_2xx(salida[0], salida[2][:300])
    proyecto_id = json.loads(salida[2].decode("utf-8"))["datos"]["proyecto"]["id"]
    esc = app.despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenarios",
        dict(IDENTIDAD_HEADERS),
        json.dumps({
            "tipo": "A", "titulo": "Escenario A",
            "parametros": {"costo": 40.0, "beneficio": 70.0, "riesgo": 25.0},
        }).encode("utf-8"),
    )
    assert_2xx(esc[0], esc[2][:300])
    escenario_id = json.loads(esc[2].decode("utf-8"))["datos"]["escenario"]["id"]
    ev = app.despachar(
        "POST",
        "/laboratorio/api/v1/projects/" + proyecto_id + "/scenarios/" + escenario_id + "/evaluate",
        dict(IDENTIDAD_HEADERS), b"",
    )
    assert_2xx(ev[0], ev[2][:300])
    outbox = app.contenedor.obtener("outbox")
    stats = outbox.estadisticas()
    assert "pendiente" in stats


def test_app_recupera_tras_reinicio_con_bd_real():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "recuperacion.db")
        app1 = montar_aplicacion(ruta)
        app1.despachar(
            "POST", "/laboratorio/api/v1/projects",
            dict(IDENTIDAD_HEADERS),
            json.dumps({"titulo": "Sobreviviente", "tipo": "negocio"}).encode("utf-8"),
        )
        del app1
        app2 = montar_aplicacion(ruta)
        salida = app2.despachar(
            "GET", "/laboratorio/api/v1/projects",
            dict(IDENTIDAD_HEADERS), b"",
        )
        assert_2xx(salida[0], salida[2][:300])
        datos = json.loads(salida[2].decode("utf-8"))
        titulos = [p["titulo"] for p in datos["datos"]["proyectos"]]
        assert "Sobreviviente" in titulos


def test_decorador_idempotente_no_repite_ejecucion():
    llamadas = {"n": 0}

    @idempotente
    def operacion_cara(x, y=0):
        llamadas["n"] += 1
        return x + y

    assert operacion_cara(1, y=2) == 3
    assert operacion_cara(1, y=2) == 3
    assert llamadas["n"] == 1
    assert operacion_cara.ejecuciones == 1
    assert operacion_cara.aciertos == 1


def test_outbox_no_duplica_entregas_procesadas(app):
    outbox = app.contenedor.obtener("outbox")
    entregados = []

    def _entregador(destino, carga):
        entregados.append(destino)

    outbox.encolar("ev.test", "zyra/documents/seal", {"a": 1})
    res1 = outbox.procesar(_entregador)
    res2 = outbox.procesar(_entregador)
    assert res1["enviados"] == 1
    assert res2["enviados"] == 0
    assert len(entregados) == 1
