"""Seguridad: ZID, roles, permisos y sobre de errores."""
import json

from apps.laboratorio.infrastructure.security.zid_auth import extraer_identidad
from apps.laboratorio.tests.conftest import assert_2xx


def test_zid_ausente_rechaza_401(despachar):
    status, _h, datos = despachar("GET", "/laboratorio/api/v1/projects", con_identidad=False)
    assert status == 401


def test_zid_invalido_rechaza():
    import pytest
    headers = {"x-zyra-zid": "!!invalido!!", "x-zyra-roles": "LAB_GOBERNADOR"}
    with pytest.raises(ValueError):
        extraer_identidad(headers)


def test_espectador_no_crea_proyectos(app):
    headers = {"x-zyra-zid": "espectador-test", "x-zyra-roles": "LAB_ESPECTADOR"}
    salida = app.despachar(
        "POST", "/laboratorio/api/v1/projects", headers,
        json.dumps({"titulo": "Denegado", "tipo": "negocio"}).encode("utf-8"),
    )
    assert salida[0] == 403, salida[2][:300]
    datos = json.loads(salida[2].decode("utf-8"))
    assert datos["error"]["codigo"] == "permiso_denegado"


def test_intermediario_convierte_excepciones_en_sobre(app):
    headers = {"x-zyra-zid": "test-g", "x-zyra-roles": "LAB_GOBERNADOR"}
    salida = app.despachar(
        "GET", "/laboratorio/api/v1/projects/proy-inexistente", headers, b"",
    )
    assert salida[0] == 404
    datos = json.loads(salida[2].decode("utf-8"))
    assert datos["ok"] is False
    assert "error" in datos


def test_frame_pull_exige_permiso_ver(despachar):
    status, _h, datos = despachar(
        "GET", "/laboratorio/api/v1/displays/targets/disp-0001/frame",
        con_identidad=False,
    )
    assert status == 401


def test_permiso_proyectar_para_registrar_destino(despachar):
    cuerpo = json.dumps({
        "tipo": "web", "direccion": "", "nombre": "seguridad-test",
    }).encode("utf-8")
    status, _h, datos = despachar(
        "POST", "/laboratorio/api/v1/displays/targets", cuerpo,
    )
    assert_2xx(status, datos)
    assert datos.get("id") or "id" in (datos.get("datos") or {}), datos
