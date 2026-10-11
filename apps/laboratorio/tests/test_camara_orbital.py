"""EX-3: camara orbital + render 2.5D determinista."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.renderer_3d import (
    CamaraOrbital, MotorRenderOrbital,
)
from apps.laboratorio.shared.exceptions.render_errors import EscenaVaciaError
from apps.laboratorio.tests.conftest import OBJETOS, assert_2xx, construir_escena, construir_escena_vacia


def test_girar_con_limites():
    cam = CamaraOrbital()
    cam.girar(90, 10)
    assert cam.estado()["azimut"] == 90.0
    assert cam.estado()["elevacion"] == 45.0
    cam.girar(0, 200)
    assert cam.estado()["elevacion"] == 85.0


def test_distancia_validada():
    with pytest.raises(ValueError):
        CamaraOrbital(distancia=0.5)
    with pytest.raises(ValueError):
        CamaraOrbital(elevacion=120)


def test_render_orbital_png_determinista():
    motor = MotorRenderOrbital()
    cam = CamaraOrbital()
    cam.girar(45, 40)
    r1 = motor.renderizar_orbital(construir_escena(), {"ancho": 200, "alto": 150}, cam)
    r2 = motor.renderizar_orbital(construir_escena(), {"ancho": 200, "alto": 150}, cam)
    assert bytes(r1.imagen_bytes[:8]) == b"\x89PNG\r\n\x1a\n"
    assert r1.imagen_bytes == r2.imagen_bytes
    assert "orbital" in r1.metadata["proyeccion"]


def test_render_orbital_rechaza_escena_vacia():
    with pytest.raises(EscenaVaciaError):
        MotorRenderOrbital().renderizar_orbital(construir_escena_vacia(), {}, CamaraOrbital())


def test_camara_por_http(despachar):
    _s, _h, datos = despachar("POST", "/laboratorio/api/v1/projects", json.dumps({
        "titulo": "Proy camara", "tipo": "negocio"}).encode("utf-8"))
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    status, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        json.dumps({"nombre": "S cam", "objetos": OBJETOS}).encode("utf-8"))
    assert_2xx(status, datos2)
    escena_id = datos2["datos"]["escena"]["id"]
    status3, headers3, _p3 = despachar(
        "POST", "/laboratorio/api/v1/scenes/" + escena_id + "/camara/orbital",
        json.dumps({"azimut": 45, "elevacion": 40}).encode("utf-8"))
    assert_2xx(status3, headers3)
    assert headers3.get("Content-Type") == "image/png"
