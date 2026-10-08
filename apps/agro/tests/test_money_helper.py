import pytest
from decimal import Decimal
from apps.agro.shared.money import (
    D2, money_str, is_positive_money, safe_float,
    sum_money)


def test_d2_half_up_regla61() -> None:
    assert money_str("2.675") == "2.68"
    assert money_str("1.005") == "1.01"
    assert money_str("-1.239") == "-1.24"
    assert money_str(3) == "3.00"
    assert money_str("10") == "10.00"
    assert D2(Decimal("7.129")) == Decimal("7.13")
    assert str(D2("2.5")) == "2.50"
    print("OK A-2 prep: D2 cuantiza 2d con HALF_UP (regla 61) desde str/int/Decimal")


def test_d2_rechaza_invalidos_honesto() -> None:
    with pytest.raises(ValueError):
        D2("abc")
    with pytest.raises(ValueError):
        D2(None)
    with pytest.raises(ValueError):
        D2(float("nan"))
    with pytest.raises(ValueError):
        D2(float("inf"))
    print("OK A-2 prep: montos invalidos -> ValueError honesto (regla 66: nunca NaN/inf silencioso)")


def test_is_positive_y_suma() -> None:
    assert is_positive_money("0.01") is True
    assert is_positive_money("0.00") is False
    assert is_positive_money("-5") is False
    assert is_positive_money("junk") is False
    assert sum_money(["0.1", "0.2"]) == "0.30"
    assert sum_money(["1.005", "2.005"]) == "3.02"
    assert sum_money([]) == "0.00"
    assert sum_money(None) == "0.00"
    print("OK A-2 prep: is_positive seguro (reemplaza float()>0) + suma exacta sin error binario")


def test_safe_float_tras_cuantizar() -> None:
    assert safe_float("12.345") == 12.35
    assert safe_float("7") == 7.0
    with pytest.raises(ValueError):
        safe_float("junk")
    print("OK A-2 prep: safe_float SOLO despues de cuantizar (frontera REAL hasta migracion 3d)")
