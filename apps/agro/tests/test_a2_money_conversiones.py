import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.agro.shared.money import safe_float
from apps.agro.modules.comercializacion.mercado.market_service import (
    MarketService, add_price_db, market_snapshot_db)
from apps.agro.modules.comercializacion.venta_simple.simple_sale_service import (
    publish_sale_db, place_offer_db, accept_offer_db,
    pay_sale_db)
from apps.agro.modules.produccion.planificacion.planning_service import (
    create_plan_db, add_plan_cost_db,
    plan_costs_summary_db)
try:
    from apps.agro.modules.recursos_y_activos.valoracion.valuation_service import (
        value_asset_db, latest_value_of_db)
except ImportError:
    from apps.agro.modules.recursos_y_activos.valoracion.valuacion_service import (
        value_asset_db, latest_value_of_db)


def _db(tmp_path):
    return SQLiteAdapter(tmp_path / "m.db")


def test_market_quantizado(tmp_path) -> None:
    db = _db(tmp_path)
    r = add_price_db(db, product="MAIZ",
        price="10.005", actor="T")
    assert r["price"] == 10.01
    row = db.query_one(
        "SELECT price FROM agro_market_prices"
        " WHERE product = ?", ("MAIZ",))
    assert float(row["price"]) == 10.01
    add_price_db(db, product="MAIZ", price=20.0,
        actor="T")
    snap = market_snapshot_db(db, "MAIZ")
    assert snap["minimum"] == 10.01
    assert snap["maximum"] == 20.0
    assert snap["average"] == 15.01
    s2 = MarketService().snapshot("FRIJOL",
                                  ["0.1", "0.2"])
    assert s2["average"] == 0.15
    assert s2["minimum"] == 0.1
    print("OK A-2 market: precio cuantizado 2d HALF_UP en escritura y lectura + promedio via Decimal")


def test_ventas_ciclo_cuantizado(tmp_path) -> None:
    db = _db(tmp_path)
    pub = publish_sale_db(db, producer_id="P1",
        product="MAIZ", quantity=10.0)
    sid = pub["sale_id"]
    of = place_offer_db(db, sale_id=sid,
        buyer="B1", amount="99.999")
    assert of["amount"] == 100.0
    orow = db.query_one(
        "SELECT amount FROM agro_sale_offers"
        " WHERE offer_id = ?",
        (of["offer_id"],))
    assert float(orow["amount"]) == 100.0
    acc = accept_offer_db(db,
        offer_id=of["offer_id"], actor="T")
    assert acc["total"] == float(
        f"{acc['total']:.2f}")
    pay = pay_sale_db(db, sale_id=sid, actor="T")
    t = pay["total"]
    assert t == float(f"{t:.2f}")
    srow = db.query_one(
        "SELECT total FROM agro_sales_plus"
        " WHERE sale_id = ?", (sid,))
    assert float(srow["total"]) == t
    print("OK A-2 ventas: oferta y total SIEMPRE a 2 decimales en retorno y almacenamiento")


def test_plan_costs_suma_exacta(tmp_path) -> None:
    db = _db(tmp_path)
    db.execute(
        "CREATE TABLE IF NOT EXISTS agro_units ("
        " unit_id TEXT PRIMARY KEY, producer_id TEXT"
        " NOT NULL, name TEXT NOT NULL, unit_type TEXT"
        " NOT NULL, land_id TEXT, created_at TEXT,"
        " closed_at TEXT, closed_by TEXT)")
    db.execute(
        "INSERT INTO agro_units (unit_id, producer_id,"
        " name, unit_type, created_at)"
        " VALUES ('U-1', 'P1', 'Finca Norte',"
        " 'parcela', '2026-01-01')")
    plan = create_plan_db(db, producer_id="P1",
        unit_id="U-1", crop="MAIZ", target=100.0)
    pid = plan["plan_id"]
    c1 = add_plan_cost_db(db, plan_id=pid,
        concept="semilla", amount="10.005",
        currency="USD")
    assert c1["amount"] == 10.01
    add_plan_cost_db(db, plan_id=pid,
        concept="flete", amount="0.1",
        currency="USD")
    add_plan_cost_db(db, plan_id=pid,
        concept="bolsas", amount="0.2",
        currency="USD")
    summ = plan_costs_summary_db(db, pid)
    assert summ["total_by_currency"]["USD"] \
        == 10.31
    print("OK A-2 plan costs: monto cuantizado + total por moneda EXACTO via Decimal")


def test_valuacion_cuantizada(tmp_path) -> None:
    db = _db(tmp_path)
    v = value_asset_db(db, producer_id="P1",
        asset_kind="TRACTOR", asset_id="A-1",
        amount="1234.567", currency="USD")
    assert v["amount"] == 1234.57
    row = db.query_one(
        "SELECT amount FROM agro_valuations"
        " WHERE asset_id = ?", ("A-1",))
    assert float(row["amount"]) == 1234.57
    lat = latest_value_of_db(db, "P1", "A-1")
    assert float(lat["amount"]) == 1234.57
    with pytest.raises(ValueError):
        value_asset_db(db, producer_id="P1",
            asset_kind="TRACTOR",
            asset_id="A-2", amount="-5",
            currency="USD")
    print("OK A-2 valuacion: monto 2d en retorno y almacenamiento; negativo rechazado por el motor dueno")
