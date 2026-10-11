"""Ciudadanos simulados + fisica real: deterministas y honestos."""
import pytest

from apps.laboratorio.infrastructure.providers.citizens_engine import MotorCiudadanos
from apps.laboratorio.infrastructure.providers.physics_engine import MotorFisico


def _poblacion():
    motor = MotorCiudadanos()
    motor.poblar(
        [
            {"origen": "descripcion", "nombre": "Ana", "rol": "madre",
             "x": 10, "y": 10, "velocidad": 1.5, "agenda": [[50, 50], [100, 20]]},
            {"origen": "descripcion", "nombre": "Luis", "rol": "vendedor",
             "x": 12, "y": 11, "velocidad": 1.2, "agenda": [[52, 52]]},
            {"origen": "escaneo", "nombre": "Visitante-1",
             "puntos": [[30, 30]], "agenda": [[80, 80]]},
        ],
        salidas=[[0, 0]],
    )
    return motor


def test_poblar_descripcion_y_escaneo():
    motor = _poblacion()
    assert motor.total() == 3


def test_origen_invalido_rechazado():
    motor = MotorCiudadanos()
    with pytest.raises(ValueError):
        motor.poblar([{"origen": "teletransporte", "nombre": "X"}])


def test_paso_determinista():
    a, b = _poblacion(), _poblacion()
    r1 = [a.paso(1.0) for _ in range(5)]
    r2 = [b.paso(1.0) for _ in range(5)]
    assert r1 == r2
    estado = a.estado_poblacion()
    assert estado["poblacion"] == 3
    assert estado["ciudadanos"][0]["x"] > 10.0


def test_aglomeracion_detectada():
    motor = MotorCiudadanos()
    motor.poblar([
        {"origen": "descripcion", "nombre": "C" + str(i),
         "x": 100 + (i % 3), "y": 100 + (i // 3),
         "velocidad": 0.1, "agenda": [[100, 100]]}
        for i in range(8)
    ])
    assert motor.paso(1.0)["aglomeraciones"]


def test_evacuacion_requiere_salidas():
    motor = MotorCiudadanos()
    motor.poblar([{"origen": "descripcion", "nombre": "A", "x": 5, "y": 5}])
    with pytest.raises(ValueError):
        motor.evacuar()


def test_evacuacion_manda_todos_a_salida():
    motor = _poblacion()
    assert motor.evacuar()["evacuando"] == 3
    for _ in range(100):
        motor.paso(1.0)
    for c in motor.estado_poblacion()["ciudadanos"]:
        assert c["estado"] == "evacuando"


def test_fisica_caida_libre():
    fis = MotorFisico(gravedad=9.81, friccion=0.0)
    fis.agregar("bola", 0, 0, 4, 4, masa=2.0)
    r = fis.paso(0.1)
    assert fis.estado()["cuerpos"][0]["vy"] > 0
    assert r["tiempo"] == pytest.approx(0.1, abs=1e-6)


def test_fisica_colision_rebota():
    fis = MotorFisico(gravedad=0.0, friccion=0.0)
    fis.agregar("a", 0, 0, 10, 10, masa=1.0, rebote=0.9)
    fis.agregar("b", 8, 0, 10, 10, masa=1.0, rebote=0.9)
    fis.impulso("a", 10, 0)
    r = fis.paso(0.016)
    assert r["total_colisiones"] >= 1
    assert r["colisiones"][0]["normal"] == "x"


def test_fisica_rechaza_dt_invalido():
    fis = MotorFisico()
    fis.agregar("c", 0, 0, 2, 2)
    with pytest.raises(ValueError):
        fis.paso(1.0)
