
"""money.py (A-2 prep) - FRONTERA DE DINERO de
AGRO (regla 61: montos SIEMPRE Decimal 2d,
fiscal = HALF_UP).

D2(value) -> Decimal cuantizado a 0.01 con
HALF_UP (acepta str/int/Decimal/float via
str(); rechaza inválidos con ValueError
honesto — NUNCA NaN/inf silencioso).
money_str(value) -> str 2d (lo que se guarda
en TEXT de la db).
is_positive_money(value) -> bool seguro
(reemplaza el patron float(value) > 0 de
shared/utils.py en la frontera).
safe_float(value) -> float SOLO DESPUES de
cuantizar (para columnas SQLite REAL hasta
la migracion completa del 3d).
sum_money(iterable) -> str 2d (suma exacta,
sin acumulacion de error binario).

RUN 3d convertira los 4 services de dinero
(market/simple_sale/valuation/planning) a
usar esta frontera en escritura y lectura."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation, \
    ROUND_HALF_UP

_Q = Decimal("0.01")


def D2(value) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError,
            ValueError):
        raise ValueError(
            "monto invalido: " + repr(value))
    if not d.is_finite():
        raise ValueError(
            "monto no finito: " + repr(value))
    return d.quantize(_Q,
                      rounding=ROUND_HALF_UP)


def money_str(value) -> str:
    return str(D2(value))


def is_positive_money(value) -> bool:
    try:
        return D2(value) > Decimal("0.00")
    except ValueError:
        return False


def safe_float(value) -> float:
    """Solo tras cuantizar (frontera REAL)."""
    return float(D2(value))


def sum_money(values) -> str:
    total = Decimal("0.00")
    for v in (values or []):
        total += D2(v)
    return str(total)
