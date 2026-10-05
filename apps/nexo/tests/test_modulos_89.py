
"""Tests L5b: modulos 8 y 9."""
from __future__ import annotations
from apps.nexo.module.modulo_8_gobierno import (
    emit as emit8, get_gov8_events,
    Modulo8Gobierno)
from apps.nexo.module.modulo_9_meta_gobierno import (
    emit as emit9, get_meta9_events,
    Modulo9MetaGobierno, SUBMENUS_M9)

def test_modulo8_12_subdominios() -> None:
    m8 = Modulo8Gobierno()
    subs = m8.get_subdominios()
    assert len(subs) == 12, str(subs)
    r = m8.nucleo_gobierno()
    assert r["modulo"] == "M8"
    r2 = m8.modo_crisis()
    assert r2["subdominio"] == "Modo Crisis / Emergencia"
    print("OK m8: 12 subdominios")

def test_modulo8_eventos() -> None:
    emit8("M8_TEST")
    events = get_gov8_events()
    assert events[-1]["event"] == "M8_TEST"
    print("OK m8: eventos")

def test_modulo9_11_subdominios() -> None:
    subs = Modulo9MetaGobierno().get_subdominios()
    assert len(subs) == 11, str(subs)
    r = Modulo9MetaGobierno().entrar("SOBERANIA_DEL_SISTEMA")
    assert r["total"] == 5
    events = get_meta9_events()
    assert events[-1]["event"] == "M9_SOBERANIA_DEL_SISTEMA"
    print("OK m9: 11 subdominios + entrar")

def test_modulo9_zeroin_out() -> None:
    m9 = Modulo9MetaGobierno()
    m9.zyra_in()
    m9.zyra_out()
    events = get_meta9_events()
    tipos = [e["event"] for e in events]
    assert "MODULO_9_ENTRADA" in tipos
    assert "MODULO_9_SALIDA" in tipos
    print("OK m9: zyra_in/zyra_out")
