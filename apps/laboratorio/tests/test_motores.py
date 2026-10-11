"""Motores: render PBR, glTF/GLB, Monte Carlo, salidas universales."""
import json
import struct

import pytest

from apps.laboratorio.infrastructure.providers.generation_engine import MotorGeneracionReal
from apps.laboratorio.infrastructure.providers.monte_carlo_engine import MotorMonteCarlo
from apps.laboratorio.infrastructure.providers.renderer_photoreal import MotorRenderFotoreal
from apps.laboratorio.infrastructure.providers.display_holo3d import MotorHolo3D
from apps.laboratorio.infrastructure.providers.png_encoder import encode_png_rgb
from apps.laboratorio.shared.exceptions.render_errors import EscenaVaciaError
from apps.laboratorio.tests.conftest import construir_escena, construir_escena_vacia


def test_pbr_genera_png_valido_con_profundidad():
    resultado = MotorRenderFotoreal().renderizar(construir_escena(), {"muestras": 1})
    assert bytes(resultado.imagen_bytes[:8]) == b"\x89PNG\r\n\x1a\n"
    assert bytes(resultado.profundidad_bytes[:8]) == b"\x89PNG\r\n\x1a\n"
    assert resultado.metadata["brdf"] == "GGX Cook-Torrance"
    assert resultado.metadata["tonemap"] == "ACES"


def test_pbr_rechaza_escena_vacia():
    with pytest.raises(EscenaVaciaError):
        MotorRenderFotoreal().renderizar(construir_escena_vacia(), {})


def test_gltf_2_0_json_real():
    gltf = json.loads(
        MotorGeneracionReal().generar(construir_escena(), "modelo").decode("utf-8")
    )
    assert gltf["asset"]["version"] == "2.0"
    assert len(gltf["meshes"]) == 2
    assert gltf["buffers"][0]["uri"].startswith("data:application/octet-stream;base64,")


def test_glb_binario_real():
    glb = MotorGeneracionReal().generar(construir_escena(), "modelo_glb")
    magico, version, total = struct.unpack("<III", glb[:12])
    assert (magico, version, total) == (0x46546C67, 2, len(glb))
    largo_json, tipo_json = struct.unpack("<II", glb[12:20])
    assert tipo_json == 0x4E4F534A
    base = 20 + largo_json
    _largo_bin, tipo_bin = struct.unpack("<II", glb[base:base + 8])
    assert tipo_bin == 0x004E4942


def test_monte_carlo_reproducible():
    mc = MotorMonteCarlo()
    config = {
        "variables": {
            "costo": {"dist": "normal", "media": 45.0, "desv": 8.0},
            "beneficio": {"dist": "uniforme", "minimo": 55.0, "maximo": 90.0},
            "riesgo": {"dist": "triangular", "minimo": 10.0, "modo": 30.0, "maximo": 70.0},
        },
        "corridas": 3000,
        "semilla": 42,
    }
    r1 = mc.simular(config)
    r2 = mc.simular(config)
    assert r1 == r2
    assert r1["p5"] <= r1["p50"] <= r1["p95"]
    lo, hi = r1["ic95"]
    assert lo <= r1["media"] <= hi


def test_monte_carlo_rechaza_distribucion_invalida():
    mc = MotorMonteCarlo()
    with pytest.raises(ValueError):
        mc.simular({"variables": {
            "costo": {"dist": "cuantica", "media": 1.0},
            "beneficio": {"dist": "normal", "media": 2.0, "desv": 1.0},
            "riesgo": {"dist": "normal", "media": 3.0, "desv": 1.0},
        }})


def test_salida_universal_web_pull():
    disp = MotorHolo3D()
    registro = disp.registrar_destino("web", "", "test-movil")
    frame = encode_png_rgb(8, 8, bytes(8 * 8 * 3))
    entrega = disp.presentar(frame, {})
    assert entrega["entregado"] is True
    recuperado, mime = disp.frame_actual(registro["id"])
    assert recuperado == frame
    assert mime == "image/png"


def test_salida_universal_sin_destino_es_honesta():
    disp = MotorHolo3D()
    frame = encode_png_rgb(8, 8, bytes(8 * 8 * 3))
    entrega = disp.presentar(frame, {"tipo": "udp"})
    assert entrega["entregado"] is False
    assert "sin destino" in entrega["motivo"]
