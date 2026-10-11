"""EX: video AVI-MJPEG real + impresion 3D STL/G-code real."""
import json
import struct

import pytest

from apps.laboratorio.infrastructure.providers.print_3d_engine import MotorImpresion3D
from apps.laboratorio.infrastructure.providers.video_encoder import MotorVideo
from apps.laboratorio.infrastructure.providers.png_encoder import encode_png_rgb
from apps.laboratorio.tests.conftest import OBJETOS, assert_2xx


def _frame(color):
    return encode_png_rgb(32, 32, bytes(bytes(color) * (32 * 32)))


def test_video_ensambla_contenedor_valido():
    res = MotorVideo().ensamblar(
        [_frame((255, 0, 0)), _frame((0, 255, 0)),
         _frame((0, 0, 255)), _frame((255, 255, 0))], fps=8)
    video = res["video"]
    assert video[:4] == b"RIFF" and video[8:12] == b"AVI "
    assert b"MJPG" in video
    assert res["frames"] == 4 and res["fps"] == 8


def test_video_rechaza_resoluciones_distintas():
    with pytest.raises(ValueError):
        MotorVideo().ensamblar([
            encode_png_rgb(32, 32, bytes(bytes((10, 20, 30)) * (32 * 32))),
            encode_png_rgb(48, 48, bytes(bytes((10, 20, 30)) * (48 * 48)))])


def test_video_rechaza_fps_invalido():
    motor = MotorVideo()
    with pytest.raises(ValueError):
        motor.ensamblar([_frame((1, 2, 3))], fps=0)
    with pytest.raises(ValueError):
        motor.ensamblar([_frame((1, 2, 3))], fps=200)


def test_stl_binario_valido():
    res = MotorImpresion3D().generar_stl([
        {"forma": "rect", "x": 0, "y": 0, "w": 20, "h": 20, "alto_3d": 5},
        {"forma": "circle", "x": 30, "y": 0, "r": 10, "alto_3d": 8}])
    stl = res["stl_binario"]
    assert stl[:21] == b"ZYRA LABORATORIO STL "
    tris = struct.unpack("<I", stl[80:84])[0]
    assert tris == res["triangulos"] > 0
    assert len(stl) == 84 + tris * 50


def test_stl_rechaza_forma_no_imprimible():
    with pytest.raises(ValueError):
        MotorImpresion3D().generar_stl([{"forma": "texto", "contenido": "hola"}])


def test_gcode_marlin_valido():
    res = MotorImpresion3D().generar_gcode(
        [{"forma": "rect", "x": 0, "y": 0, "w": 40, "h": 40, "alto_3d": 10}],
        altura_capa_mm=0.2, densidad_relleno=0.3, velocidad_mm_s=1500)
    assert "M104 S200" in res["gcode"]
    assert "G28" in res["gcode"]
    assert "M84" in res["gcode"]
    assert res["capas"] == 50


def test_gcode_rechaza_parametros_invalidos():
    motor = MotorImpresion3D()
    objs = [{"forma": "rect", "x": 0, "y": 0, "w": 10, "h": 10}]
    with pytest.raises(ValueError):
        motor.generar_gcode(objs, altura_capa_mm=2.0)
    with pytest.raises(ValueError):
        motor.generar_gcode(objs, densidad_relleno=1.5)
    with pytest.raises(ValueError):
        motor.generar_gcode(objs, velocidad_mm_s=0)


def test_disenar_y_preparar_flujo_completo():
    res = MotorImpresion3D().disenar_y_preparar(
        [{"forma": "rect", "x": 0, "y": 0, "w": 30, "h": 30, "alto_3d": 6}],
        altura_capa_mm=0.3)
    assert res["stl"]["triangulos"] > 0
    assert res["gcode"]["capas"] == 20


def test_p3d_por_http(app, despachar):
    _s, _h, datos = despachar("POST", "/laboratorio/api/v1/projects", json.dumps({
        "titulo": "Proy EX", "tipo": "negocio"}).encode("utf-8"))
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    status, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        json.dumps({"nombre": "S", "objetos": OBJETOS}).encode("utf-8"))
    assert_2xx(status, datos2)
    escena_id = datos2["datos"]["escena"]["id"]
    status3, _h3, datos3 = despachar(
        "POST", "/laboratorio/api/v1/scenes/" + escena_id + "/print3d/stl",
        json.dumps({"objetos": [{"forma": "rect", "x": 0, "y": 0,
                                 "w": 20, "h": 20, "alto_3d": 5}]}).encode("utf-8"))
    assert_2xx(status3, datos3)
    assert datos3["datos"]["triangulos"] > 0
    status4, _h4, datos4 = despachar(
        "POST", "/laboratorio/api/v1/scenes/" + escena_id + "/print3d/gcode",
        json.dumps({"objetos": [{"forma": "rect", "x": 0, "y": 0,
                                 "w": 20, "h": 20, "alto_3d": 5}]}).encode("utf-8"))
    assert_2xx(status4, datos4)
    assert "M104" in datos4["datos"]["gcode"]
