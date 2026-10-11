"""Presentacion holografica interactiva: crear, controlar, tocar, proyectar."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.presentation_remote import (
    PresentacionRemota,
    SesionPresentacion,
)
from apps.laboratorio.infrastructure.providers.display_holo3d import MotorHolo3D
from apps.laboratorio.tests.conftest import OBJETOS, assert_2xx


class _PasoFalso:
    def __init__(self, titulo, contenido):
        self.titulo = titulo
        self.contenido = contenido

    def a_dict(self):
        return {"titulo": self.titulo, "contenido": self.contenido}


class _PresentacionFalsa:
    id = "pres-test"
    pasos = [
        _PasoFalso("Inicio", "Bienvenidos al proyecto"),
        _PasoFalso("Modelo 3D", "Este es el modelo"),
        _PasoFalso("Cierre", "Preguntas"),
    ]


def _gestor():
    repo = type("R", (), {"obtener_exigir": staticmethod(lambda pid: _PresentacionFalsa())})()
    return PresentacionRemota(repo, MotorHolo3D())


def _sesion():
    return SesionPresentacion("ses-test", _PresentacionFalsa(), MotorHolo3D())


def test_crear_sesion_con_pasos_reales():
    res = _gestor().crear_sesion("pres-test")
    assert res["total_pasos"] == 3
    assert isinstance(res["sesion"], str) and res["sesion"]
    assert "view" in res["vista_control"]


def test_sesion_desconocida_rechaza():
    with pytest.raises(ValueError):
        _gestor().sesion("fantasma")


def test_avanzar_retroceder_ir_a():
    s = _sesion()
    assert s.avanzar()["paso"] == 1
    assert s.avanzar()["paso"] == 2
    assert s.avanzar()["paso"] == 2
    assert s.retroceder()["paso"] == 1
    assert s.ir_a(0)["paso"] == 0
    with pytest.raises(ValueError):
        s.ir_a(99)


def test_tocar_punto_registra_anotacion():
    s = _sesion()
    a = s.tocar_punto(120.5, 80.2, "entrada")
    assert a["paso"] == 0 and a["x"] == 120.5
    assert len(s.anotaciones_del_paso(0)) == 1
    assert s.anotaciones_del_paso(1) == []
    with pytest.raises(ValueError):
        s.tocar_punto(-1, 0)


def test_frame_holograma_incluye_titulo_y_anotaciones():
    s = _sesion()
    s.tocar_punto(100, 100, "punto clave")
    frame = s.frame_holograma().decode("utf-8")
    assert "<svg" in frame and "Inicio" in frame and "circle" in frame


def test_proyectar_paso_actual_por_salida_universal():
    gestor = _gestor()
    res = gestor.crear_sesion("pres-test")
    salida = gestor.proyectar_paso_actual(res["sesion"])
    assert salida["paso"] == 0
    assert salida["proyeccion"]["entregado"] is True


def test_finalizar_devuelve_historial_completo():
    s = _sesion()
    s.avanzar()
    s.tocar_punto(10, 10)
    res = s.finalizar()
    assert res["anotaciones"] == 1
    acciones = [h["accion"] for h in res["historial"]]
    assert "avanzar" in acciones and "tocar_punto" in acciones and "finalizar" in acciones


def test_ciclo_completo_por_http(despachar):
    _s, _h, datos = despachar("POST", "/laboratorio/api/v1/projects", json.dumps({
        "titulo": "Proy presentacion", "tipo": "negocio",
    }).encode("utf-8"))
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    status_sc, _hs, datos_sc = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        json.dumps({"nombre": "Escena presentacion", "objetos": OBJETOS}).encode("utf-8"))
    assert_2xx(status_sc, datos_sc)
    escena_id = datos_sc["datos"]["escena"]["id"]
    status, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/presentations",
        json.dumps({"titulo": "Mi presentacion", "pasos": [
            {"titulo": "Inicio", "contenido": "Hola", "duracion_segundos": 30, "escena_id": escena_id},
            {"titulo": "Demo", "contenido": "Mira", "duracion_segundos": 45, "escena_id": escena_id},
        ]}).encode("utf-8"))
    assert_2xx(status, datos2)
    presentacion_id = datos2["datos"]["presentacion"]["id"]
    status3, _h3, datos3 = despachar(
        "POST", "/laboratorio/api/v1/presentations/remote",
        json.dumps({"presentacion_id": presentacion_id}).encode("utf-8"))
    assert_2xx(status3, datos3)
    sesion_id = datos3.get("sesion") or (datos3.get("datos") or {}).get("sesion")
    assert sesion_id, datos3
    status4, _h4, datos4 = despachar(
        "POST", "/laboratorio/api/v1/presentations/remote/" + sesion_id + "/accion",
        json.dumps({"accion": "avanzar"}).encode("utf-8"))
    assert_2xx(status4, datos4)
    assert datos4.get("paso") == 1
    status5, _h5, datos5 = despachar(
        "POST", "/laboratorio/api/v1/presentations/remote/" + sesion_id + "/tocar",
        json.dumps({"x": 200, "y": 150, "etiqueta": "aqui"}).encode("utf-8"))
    assert_2xx(status5, datos5)
    status6, _h6, datos6 = despachar("GET", "/laboratorio/api/v1/presentations/remote/" + sesion_id)
    assert_2xx(status6, datos6)
    anots = datos6.get("anotaciones_total") or (datos6.get("datos") or {}).get("anotaciones_total")
    assert anots == 1, datos6
    status7, _h7, _d7 = despachar("GET", "/laboratorio/api/v1/presentations/remote/" + sesion_id + "/view")
    assert_2xx(status7, _d7)
