"""Ciclo completo: crear proyecto -> escena -> generar artefacto."""
import json

from apps.laboratorio.tests.conftest import assert_2xx


def _post(despachar, ruta, cuerpo):
    return despachar("POST", ruta, json.dumps(cuerpo).encode("utf-8"))


def test_crear_proyecto_y_listar(despachar):
    status, _h, datos = _post(despachar, "/laboratorio/api/v1/projects", {
        "titulo": "Proyecto de prueba",
        "descripcion": "ciclo completo",
        "tipo": "negocio",
    })
    assert_2xx(status, datos)
    proyecto = datos["datos"]["proyecto"]
    assert proyecto["titulo"] == "Proyecto de prueba"
    status2, _h2, lista = despachar("GET", "/laboratorio/api/v1/projects")
    assert_2xx(status2, lista)
    ids = [p["id"] for p in lista["datos"]["proyectos"]]
    assert proyecto["id"] in ids


def test_crear_proyecto_sin_titulo_rechaza(despachar):
    status, _h, datos = _post(despachar, "/laboratorio/api/v1/projects", {"titulo": ""})
    assert status == 400
    assert datos["error"]["codigo"] == "valor_invalido"


def test_crear_escena_y_generar_imagen(despachar):
    _s, _h, datos = _post(despachar, "/laboratorio/api/v1/projects", {
        "titulo": "Con escena", "tipo": "negocio",
    })
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    status, _h2, datos2 = _post(
        despachar,
        "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        {
            "nombre": "Escena 1",
            "objetos": [
                {"forma": "rect", "x": 5, "y": 5, "w": 40, "h": 20, "color": "#22D3EE", "capa": "fondo"},
            ],
        },
    )
    assert_2xx(status, datos2)
    escena_id = datos2["datos"]["escena"]["id"]
    status3, _h3, datos3 = _post(
        despachar,
        "/laboratorio/api/v1/scenes/" + escena_id + "/generate",
        {"formato": "imagen"},
    )
    assert_2xx(status3, datos3)
    artefacto = datos3["datos"]["artefacto"]
    assert artefacto["formato"] == "imagen"
