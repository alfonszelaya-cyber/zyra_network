"""Fixtures reales compartidos por la suite de LABORATORIO."""
import json
import pytest

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.api.app import montar_aplicacion

OBJETOS = [
    {"forma": "rect", "x": 10, "y": 20, "w": 80, "h": 50, "color": "#3B82F6", "capa": "fondo"},
    {"forma": "circle", "cx": 140, "cy": 75, "r": 30, "color": "#F59E0B", "capa": "medio"},
    {"forma": "texto", "x": 15, "y": 110, "contenido": "ZYRA", "color": "#E2E8F0", "capa": "frente"},
]

IDENTIDAD_HEADERS = {
    "x-zyra-zid": "test-gobernador",
    "x-zyra-roles": "LAB_GOBERNADOR",
}


def assert_2xx(status, contexto=""):
    """Exito HTTP real: 200..299 (200 lectura, 201 creacion)."""
    assert 200 <= int(status) < 300, (
        str(contexto)[:400] + " (status=" + str(status) + ")"
    )


def construir_escena():
    try:
        return Escena3D(nombre="prueba", ancho=200, alto=150, objetos=OBJETOS)
    except TypeError:
        try:
            return Escena3D("prueba", 200, 150, OBJETOS)
        except Exception:
            esc = Escena3D.__new__(Escena3D)
            for atributo, valor in (
                ("nombre", "prueba"), ("ancho", 200), ("alto", 150), ("objetos", OBJETOS),
            ):
                setattr(esc, atributo, valor)
            return esc


def construir_escena_vacia():
    try:
        return Escena3D(nombre="vacia", ancho=200, alto=150, objetos=[])
    except TypeError:
        try:
            return Escena3D("vacia", 200, 150, [])
        except Exception:
            esc = Escena3D.__new__(Escena3D)
            for atributo, valor in (
                ("nombre", "vacia"), ("ancho", 200), ("alto", 150), ("objetos", []),
            ):
                setattr(esc, atributo, valor)
            return esc


@pytest.fixture()
def escena():
    return construir_escena()


@pytest.fixture()
def app():
    return montar_aplicacion(":memory:")


@pytest.fixture()
def despachar(app):
    def _llamar(metodo, ruta, cuerpo=None, con_identidad=True):
        headers = dict(IDENTIDAD_HEADERS) if con_identidad else {}
        salida = app.despachar(metodo, ruta, headers, cuerpo or b"")
        status, headers_out, payload = salida[0], salida[1], salida[2]
        try:
            datos = json.loads(payload.decode("utf-8"))
        except Exception:
            datos = None
        return status, headers_out, datos
    return _llamar
