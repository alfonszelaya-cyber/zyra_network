import pytest
from apps.nexo.module import discover_menus
from apps.nexo.routers.modules_router import (list_menus,
                                              get_menu)

def test_registry_descubre_149() -> None:
    menus = discover_menus()
    assert len(menus) == 149
    ids = [m["menu_id"] for m in menus]
    assert len(set(ids)) == 149
    for m in menus:
        assert m["title"].strip()
        assert len(m["options"]) >= 1
        for o in m["options"]:
            assert o["key"] and o["label"]
        assert not m["menu_id"].endswith(".menu")
    print("OK registry: 149 menus unicos, ids sin sufijo")

def test_regla70_sin_logistica() -> None:
    menus = discover_menus()
    logi = [m for m in menus
            if "logistica" in m["path"]]
    assert logi == []
    ops = list_menus(module="operaciones")
    assert ops["total"] == 12
    for m in ops["menus"]:
        assert "logistica" not in m["path"]
    print("OK regla 70: cero menus de logistica en NEXO")

def test_router_y_menus_clave() -> None:
    m = get_menu("accounting.asientos")
    assert m is not None
    assert m["module"] == "accounting"
    labels = " ".join(o["label"].lower()
                      for o in m["options"])
    assert "asiento" in labels
    assert get_menu("no.existe") is None
    total = list_menus()["total"]
    assert total == 149
    r = list_menus(module="risk")
    assert r["total"] == 14
    fo = list_menus(module="family_office")
    assert fo["total"] == 17
    print("OK router: list/get + modulos clave con conteo exacto")
