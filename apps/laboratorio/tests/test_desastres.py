"""EX-DES: desastre -> zonas seguras + ayuda + evento a la Red."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.citizens_engine import MotorCiudadanos
from apps.laboratorio.tests.conftest import OBJETOS, assert_2xx


def _motor():
    motor = MotorCiudadanos()
    motor.poblar(
        [{"origen": "descripcion", "nombre": "P" + str(i),
          "x": 10 + i, "y": 10, "velocidad": 1.0, "agenda": [[60, 60]]}
         for i in range(5)]
        + [{"origen": "descripcion", "nombre": "Lejos",
            "x": 500, "y": 500, "velocidad": 1.0, "agenda": [[510, 510]]}],
        salidas=[[0, 0]])
    return motor


def test_desastre_desconocido_rechaza():
    with pytest.raises(ValueError):
        _motor().simular_desastre("meteorito", [10, 10], 50, [[200, 200, 30]])


def test_terremoto_afecta_solo_zona_y_genera_plan():
    motor = _motor()
    plan = motor.simular_desastre("terremoto", [12, 10], 30, [[300, 300, 40]])
    assert plan["afectados"] == 5
    assert plan["poblacion"] == 6
    assert "rescate urbano" in plan["ayuda_necesaria"]
    assert plan["pasos_estimados_evacuacion"] > 0
    for c in motor.estado_poblacion()["ciudadanos"]:
        assert c["estado"] == ("evacuando" if c["nombre"] != "Lejos" else "en_ruta")


def test_cada_desastre_tiene_ayuda_propia():
    motor = MotorCiudadanos()
    motor.poblar([{"origen": "descripcion", "nombre": "A", "x": 0, "y": 0}])
    assert "botes de rescate" in motor.simular_desastre("inundacion", [0, 0], 100, [[50, 50, 20]])["ayuda_necesaria"]
    assert "mascarillas" in motor.simular_desastre("erupcion", [0, 0], 100, [[80, 80, 20]])["ayuda_necesaria"]


def test_zonas_seguras_requieren_radio():
    with pytest.raises(ValueError):
        _motor().simular_desastre("incendio", [10, 10], 30, [[200, 200]])


def test_desastre_por_http_deja_evento_en_outbox(app, despachar):
    _s, _h, datos = despachar("POST", "/laboratorio/api/v1/projects", json.dumps({
        "titulo": "Proy desastre", "tipo": "negocio"}).encode("utf-8"))
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    status, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        json.dumps({"nombre": "S", "objetos": OBJETOS}).encode("utf-8"))
    assert_2xx(status, datos2)
    escena_id = datos2["datos"]["escena"]["id"]
    status3, _h3, datos3 = despachar(
        "POST", "/laboratorio/api/v1/scenes/" + escena_id + "/citizens/populate",
        json.dumps({"ciudadanos": [
            {"origen": "descripcion", "nombre": "C1", "x": 10, "y": 10},
            {"origen": "descripcion", "nombre": "C2", "x": 12, "y": 11}],
            "salidas": [[0, 0]]}).encode("utf-8"))
    assert_2xx(status3, datos3)
    status4, _h4, datos4 = despachar(
        "POST", "/laboratorio/api/v1/scenes/" + escena_id + "/desastre/simular",
        json.dumps({"tipo": "terremoto", "epicentro": [11, 10], "radio": 50,
                    "zonas_seguras": [[200, 200, 40]]}).encode("utf-8"))
    assert_2xx(status4, datos4)
    assert datos4["datos"]["plan"]["afectados"] == 2
    assert app.contenedor.obtener("outbox").estadisticas()["pendiente"] >= 1
