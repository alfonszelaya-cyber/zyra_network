"""Gemelo digital en vivo - datos reales, deltas y alertas honestas."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.simulation_engine import GemeloVivo
from apps.laboratorio.tests.conftest import assert_2xx


def test_registrar_y_actualizar_con_delta():
    gem = GemeloVivo()
    gem.registrar_fuente("sensor-rio", "sensor", 2.0, umbral_alto=5.0)
    res = gem.actualizar("sensor-rio", 3.5)
    assert res["valor_anterior"] == 2.0
    assert res["valor_nuevo"] == 3.5
    assert res["delta"] == 1.5
    assert res["alertas"] == []


def test_alerta_umbral_alto_y_bajo():
    gem = GemeloVivo()
    gem.registrar_fuente("rio", "sensor", 3.0, umbral_alto=5.0, umbral_bajo=1.0)
    assert gem.actualizar("rio", 6.0)["alertas"][0]["tipo"] == "umbral_alto_superado"
    assert gem.actualizar("rio", 0.5)["alertas"][0]["tipo"] == "umbral_bajo_superado"


def test_fuente_no_registrada_rechaza():
    gem = GemeloVivo()
    with pytest.raises(ValueError):
        gem.actualizar("fantasma", 1.0)


def test_tipo_invalido_y_umbrales_invalidos_rechazan():
    gem = GemeloVivo()
    with pytest.raises(ValueError):
        gem.registrar_fuente("a", "telepatia", 1.0)
    with pytest.raises(ValueError):
        gem.registrar_fuente("b", "sensor", 1.0, umbral_alto=5.0, umbral_bajo=5.0)


def test_estado_y_historico_reales():
    gem = GemeloVivo()
    gem.registrar_fuente("api-sismos", "api", 1.0)
    gem.actualizar("api-sismos", 2.0)
    gem.actualizar("api-sismos", 4.0)
    assert gem.estado()["actualizaciones_totales"] == 2
    assert gem.historico("api-sismos")["valores"] == [1.0, 2.0, 4.0]


def test_gemelo_por_http(despachar):
    cuerpo = json.dumps({"id": "sensor-aforo", "tipo": "sensor", "valor": 10.0,
                         "umbral_alto": 20.0, "etiqueta": "aforo"}).encode("utf-8")
    status, _h, datos = despachar("POST", "/laboratorio/api/v1/twin/sources", cuerpo)
    assert_2xx(status, datos)
    status2, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/twin/sources/sensor-aforo",
        json.dumps({"valor": 25.0}).encode("utf-8"))
    assert_2xx(status2, datos2)
    assert datos2["datos"]["alertas"][0]["tipo"] == "umbral_alto_superado"
    status3, _h3, datos3 = despachar("GET", "/laboratorio/api/v1/twin")
    assert_2xx(status3, datos3)
    assert datos3["datos"]["total_fuentes"] == 1
