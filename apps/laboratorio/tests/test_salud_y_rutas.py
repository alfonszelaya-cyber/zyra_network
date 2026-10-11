"""Salud real, rutas montadas e indice publico."""
from apps.laboratorio.tests.conftest import assert_2xx


def test_salud_publica_reporta_realidad(despachar):
    status, _headers, datos = despachar("GET", "/laboratorio/health", con_identidad=False)
    assert_2xx(status, datos)
    assert datos["ok"] is True
    assert datos["datos"]["motores_total"] == 17
    assert datos["datos"]["motores_disponibles"] == 17
    assert datos["datos"]["red"]["configurada"] is False


def test_indice_publico_lista_rutas(despachar):
    status, _headers, datos = despachar("GET", "/laboratorio", con_identidad=False)
    assert_2xx(status, datos)
    assert len(datos["datos"]["rutas"]) >= 74, list(datos.keys())


def test_rutas_con_permiso_requieren_zid(despachar):
    status, _h, datos = despachar("GET", "/laboratorio/api/v1/projects", con_identidad=False)
    assert status == 401
    assert datos["error"]["codigo"] == "zid_ausente"


def test_ruta_inexistente_404(despachar):
    status, _h, datos = despachar("GET", "/laboratorio/api/v1/inexistente")
    assert status == 404, datos
    assert datos["error"]["codigo"] == "entidad_no_encontrada"
