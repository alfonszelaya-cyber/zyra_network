"""GOV-DATA: panel nacional en tiempo real desde eventos reales."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.gov_data_engine import MotorGovData
from apps.laboratorio.tests.conftest import assert_2xx


def test_ingestar_evento_real():
    gov = MotorGovData()
    reg = gov.ingestar("semilla.matriculada", {"valor": 120}, app="educacion")
    assert reg["app"] == "educacion"
    assert gov.capa_a()["total"] == 1


def test_evento_sin_nombre_rechaza():
    with pytest.raises(ValueError):
        MotorGovData().ingestar("")


def test_capa_a_delta_y_gravedad():
    gov = MotorGovData()
    gov.ingestar("nexo.factura", {"valor": 100})
    gov.ingestar("nexo.factura", {"valor": 115})
    ind = gov.capa_a()["indicadores"][0]
    assert ind["delta"] == 15.0
    assert ind["gravedad"] == "alerta"


def test_capa_b_recomendacion_critica():
    gov = MotorGovData()
    for i in range(3):
        gov.ingestar("agro.cosecha", {"valor": 50 + i * 12})
        gov.ingestar("agro.venta", {"valor": 20 + i * 15})
        gov.ingestar("agro.plaga", {"valor": 5 + i * 15})
    dominio = [d for d in gov.capa_b()["dominios"] if d["dominio"] == "agro"][0]
    assert dominio["alertas"] >= 3
    assert dominio["gravedad"] == "critica"
    assert "Intervencion" in dominio["recomendacion"]


def test_dominio_normal_sin_accion():
    gov = MotorGovData()
    gov.ingestar("subastas.venta", {"valor": 50})
    d = [d for d in gov.capa_b()["dominios"] if d["dominio"] == "comercio"][0]
    assert d["gravedad"] == "normal"
    assert "estable" in d["recomendacion"]


def test_historial_limitado():
    gov = MotorGovData()
    for i in range(10):
        gov.ingestar("axis.emergencia", {"valor": i})
    hist = gov.historial(5)
    assert hist["total"] == 10
    assert len(hist["eventos"]) == 5


def test_gov_por_http(app, despachar):
    status, _h, datos = despachar(
        "POST", "/laboratorio/api/v1/gov/eventos",
        json.dumps({"evento": "semilla.alerta.dropout", "datos": {"valor": 5},
                    "app": "educacion"}).encode("utf-8"))
    assert_2xx(status, datos)
    status2, _h2, datos2 = despachar("GET", "/laboratorio/api/v1/gov/capa-a")
    assert_2xx(status2, datos2)
    assert datos2["datos"]["total"] >= 1
    status3, _h3, datos3 = despachar("GET", "/laboratorio/api/v1/gov/capa-b")
    assert_2xx(status3, datos3)
    assert datos3["datos"]["total_dominios"] >= 1
    assert app.contenedor.obtener("outbox") is not None
