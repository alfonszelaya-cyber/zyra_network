"""Persistencia real: los datos sobreviven entre instancias."""
import json
import os
import tempfile

from apps.laboratorio.infrastructure.api.app import montar_aplicacion
from apps.laboratorio.tests.conftest import IDENTIDAD_HEADERS, assert_2xx


def test_proyecto_sobrevive_reinicio_de_app():
    with tempfile.TemporaryDirectory() as tmp:
        ruta_bd = os.path.join(tmp, "lab.db")
        app1 = montar_aplicacion(ruta_bd)
        salida = app1.despachar(
            "POST", "/laboratorio/api/v1/projects",
            dict(IDENTIDAD_HEADERS),
            json.dumps({"titulo": "Persistente", "tipo": "negocio"}).encode("utf-8"),
        )
        assert_2xx(salida[0], salida[2][:300])
        datos = json.loads(salida[2].decode("utf-8"))
        proyecto_id = datos["datos"]["proyecto"]["id"]
        app2 = montar_aplicacion(ruta_bd)
        salida2 = app2.despachar(
            "GET", "/laboratorio/api/v1/projects/" + proyecto_id,
            dict(IDENTIDAD_HEADERS), b"",
        )
        assert_2xx(salida2[0], salida2[2][:300])
        datos2 = json.loads(salida2[2].decode("utf-8"))
        assert datos2["datos"]["proyecto"]["titulo"] == "Persistente"


def test_historial_registra_operaciones():
    with tempfile.TemporaryDirectory() as tmp:
        app1 = montar_aplicacion(os.path.join(tmp, "h.db"))
        salida = app1.despachar(
            "POST", "/laboratorio/api/v1/projects",
            dict(IDENTIDAD_HEADERS),
            json.dumps({"titulo": "Historial", "tipo": "negocio"}).encode("utf-8"),
        )
        assert_2xx(salida[0], salida[2][:300])
        proyecto_id = json.loads(salida[2].decode("utf-8"))["datos"]["proyecto"]["id"]
        repo = app1.contenedor.obtener("repo_historial")
        entradas = repo.listar({"proyecto_id": proyecto_id}, 10, 0)
        assert len(entradas) >= 1
