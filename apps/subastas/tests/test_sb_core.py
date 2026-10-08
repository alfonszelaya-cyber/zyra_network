import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.subastas.auction_engine import (
    ensure_db as e1, create_auction_db, place_bid_db,
    bids_of_db, award_db, cancel_auction_db,
    auction_of_db, active_auctions_db)
from apps.subastas.registration_engine import (
    ensure_db as e2, register_subject_db, add_doc_db,
    verify_subject_db, verified_subjects_db)
from apps.subastas.escrow_finance import (
    ensure_db as e3, hold_db, release_db, refund_db,
    liquidations_of_db)
from apps.subastas.risk_protect import (
    ensure_db as e4, open_dispute_db,
    advance_dispute_db, resolve_dispute_db,
    flag_fraud_db, fraud_of_db, open_disputes_db)
from apps.subastas.logistics_intl import (
    ensure_db as e5, register_carrier_db,
    create_shipment_db, declare_customs_db,
    clear_customs_db, deliver_shipment_db)
from apps.subastas.radar_vip import (
    ensure_db as e6, watch_db, unwatch_db,
    publish_offer_db, alerts_of_db)


def test_auction_ciclo_completo(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a.db")
    e1(db)
    a = create_auction_db(db, title="Casa Colonial",
        base_price=100000.0,
        min_increment=1000.0, category="inmuebles",
        created_at="2026-01-01")
    aid = a["auction_id"]
    with pytest.raises(ValueError):
        place_bid_db(db, auction_id=aid,
            bidder="C-1", amount=500.0)
    with pytest.raises(ValueError):
        place_bid_db(db, auction_id=aid,
            bidder=" ", amount=100000.0)
    b1 = place_bid_db(db, auction_id=aid,
        bidder="C-1", amount=100000.0)
    assert b1["min_next"] == 101000.0
    with pytest.raises(ValueError):
        place_bid_db(db, auction_id=aid,
            bidder="C-2", amount=100500.0)
    place_bid_db(db, auction_id=aid,
        bidder="C-2", amount=101000.0)
    assert len(bids_of_db(db, aid)) == 2
    aw = award_db(db, aid, rate_pct=5.0,
        closed_at="2026-01-10")
    assert aw["winner_id"] == "C-2"
    assert aw["winner_bid"] == 101000.0
    assert aw["commission"] == 5050.0
    with pytest.raises(ValueError):
        place_bid_db(db, auction_id=aid,
            bidder="C-3", amount=200000.0)
    with pytest.raises(ValueError):
        award_db(db, aid)
    ao = auction_of_db(db, aid)
    assert ao["status"] == "adjudicada"
    assert ao["winner_bid"] == 101000.0
    print("OK SUB subastas: incrementos validados + adjudicacion con comision 2d (5050) + doble cierre rechazado")


def test_auction_cancel_con_pujas_bloqueada(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a2.db")
    e1(db)
    a = create_auction_db(db, title="Vehiculo",
        base_price=5000.0, created_at="2026")
    with pytest.raises(ValueError):
        cancel_auction_db(db, a["auction_id"],
            reason=" ")
    cancel_auction_db(db, a["auction_id"],
        reason="sin interesados",
        closed_at="2026-01-05")
    ao = auction_of_db(db, a["auction_id"])
    assert ao["status"] == "cancelada"
    a2 = create_auction_db(db, title="Otro",
        base_price=1000.0, created_at="2026")
    place_bid_db(db, auction_id=a2["auction_id"],
        bidder="C-1", amount=1000.0)
    with pytest.raises(ValueError):
        cancel_auction_db(db,
            a2["auction_id"],
            reason="intento con pujas")
    assert auction_of_db(
        db, a2["auction_id"])["status"] == "activa"
    print("OK SUB cancel: sin motivo rechazada + con pujas BLOQUEADA (regla 66) + closed_at propio (el reason ya no se filtra a la columna)")


def test_registro_kyc_kyb(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "r.db")
    e2(db)
    with pytest.raises(ValueError):
        register_subject_db(db, kind="COMPRADOR",
            name="X", zid=" ")
    c = register_subject_db(db, kind="COMPRADOR",
        name="Comprador VIP", zid="ZID-C1",
        created_at="2026")
    with pytest.raises(ValueError):
        register_subject_db(db, kind="EMPRESA",
            name="SA", zid="ZID-E1")
    register_subject_db(db, kind="EMPRESA",
        name="Subastas SA", tax_id="TAX-1",
        created_at="2026")
    with pytest.raises(ValueError):
        verify_subject_db(db, c["subject_id"],
            approve=True, verified_by="OP-1")
    add_doc_db(db, subject_id=c["subject_id"],
        kind="DUI", ref="REF-1",
        created_at="2026")
    v = verify_subject_db(db, c["subject_id"],
        approve=True, verified_by="OP-1",
        at="2026-01-02")
    assert v["status"] == "verificado"
    with pytest.raises(ValueError):
        verify_subject_db(db, c["subject_id"],
            approve=False, verified_by="OP-1")
    assert verified_subjects_db(
        db, "COMPRADOR")[0]["kind"] == "COMPRADOR"
    print("OK SUB registro: comprador con ZID (regla 63) + empresa con tax_id + verificacion exige documento (regla 66) + decision unica")


def test_escrow_release_refund(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "e.db")
    e3(db)
    with pytest.raises(ValueError):
        hold_db(db, auction_id="A1", buyer="C",
            seller="V", amount=1000.0,
            commission=1200.0)
    esc = hold_db(db, auction_id="A1", buyer="C",
        seller="V", amount=1000.0,
        commission=50.0, currency="USD",
        created_at="2026-01-01")
    assert esc["status"] == "retenido"
    with pytest.raises(ValueError):
        hold_db(db, auction_id="A1", buyer="C",
            seller="V", amount=-5)
    rel = release_db(db, esc["esc_id"],
        at="2026-01-05")
    assert rel["gross"] == 1000.0
    assert rel["commission"] == 50.0
    assert rel["net"] == 950.0
    with pytest.raises(ValueError):
        release_db(db, esc["esc_id"])
    esc2 = hold_db(db, auction_id="A2", buyer="C2",
        seller="V", amount=500.0, commission=10.0,
        created_at="2026-01-06")
    rf = refund_db(db, esc2["esc_id"],
        reason="no hubo entrega",
        at="2026-01-10")
    assert rf["status"] == "reembolsado"
    with pytest.raises(ValueError):
        refund_db(db, esc2["esc_id"],
            reason="otra vez")
    with pytest.raises(ValueError):
        refund_db(db, esc2["esc_id"],
            reason=" ")
    liqs = liquidations_of_db(db, "V")
    assert liqs[0]["net"] == 950.0
    print("OK SUB escrow: comision excede rechazada + release con liquidacion 2d (950) + reembolso con motivo + liquidaciones por vendedor")


def test_disputas_y_fraude_informativo(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "d.db")
    e4(db)
    d = open_dispute_db(db, auction_id="A1",
        opened_by="C-1", reason="no llego el lote",
        at="2026-01-01")
    with pytest.raises(ValueError):
        open_dispute_db(db, auction_id="A1",
            opened_by="C-2", reason=" ")
    a = advance_dispute_db(db, d["disp_id"],
        actor="OP-1")
    assert a["status"] == "en_revision"
    r = resolve_dispute_db(db, d["disp_id"],
        resolution="reembolso parcial 50%",
        resolved_by="OP-1", at="2026-01-05")
    assert r["status"] == "resuelta"
    with pytest.raises(ValueError):
        advance_dispute_db(db, d["disp_id"])
    with pytest.raises(ValueError):
        resolve_dispute_db(db, d["disp_id"],
            resolution="x",
            resolved_by="OP-1")
    f = flag_fraud_db(db, target="C-9",
        kind="pujas coordinadas", score=80,
        detail="patron detectado",
        flagged_by="SYS", at="2026-01-06")
    assert f["score"] == 80
    assert "NO censura" in f["note"]
    with pytest.raises(ValueError):
        flag_fraud_db(db, target="C-9",
            kind="x", score=150)
    assert len(fraud_of_db(db, "C-9")) == 1
    assert open_disputes_db(db) == []
    print("OK SUB riesgo: disputas 3 estados + resolucion unica + ZyraRiskScore INFORMATIVO (regla 57) + score fuera de rango rechazado")


def test_logistica_internacional_aduanas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "l.db")
    e5(db)
    cnac = register_carrier_db(db, name="Nac Express",
        scope="nacional", created_at="2026")
    cint = register_carrier_db(db, name="Global Cargo",
        scope="internacional", created_at="2026")
    with pytest.raises(ValueError):
        register_carrier_db(db, name=" ",
            scope="marcial")
    s1 = create_shipment_db(db,
        carrier_id=cnac["carrier_id"],
        origin="SAN SALVADOR",
        destination="SANTA ANA",
        auction_id="A1", at="2026-01-01")
    assert s1["scope"] == "nacional"
    s2 = create_shipment_db(db,
        carrier_id=cint["carrier_id"],
        origin="SAN SALVADOR",
        destination="MIAMI",
        auction_id="A2", at="2026-01-02")
    assert s2["scope"] == "internacional"
    with pytest.raises(ValueError):
        declare_customs_db(db, ship_id=s1["ship_id"],
            direction="EXPORTACION",
            declaration="X",
            tariff=50.0)
    cu = declare_customs_db(db, ship_id=s2["ship_id"],
        direction="EXPORTACION",
        declaration="lote de cafe 100qq",
        tariff=150.0, at="2026-01-03")
    assert cu["tariff"] == 150.0
    with pytest.raises(ValueError):
        declare_customs_db(db, ship_id=s2["ship_id"],
            direction="ESPACIAL",
            declaration="X")
    with pytest.raises(ValueError):
        deliver_shipment_db(db, s2["ship_id"],
            at="2026-01-04")
    clear_customs_db(db, cu["cust_id"],
        at="2026-01-05")
    with pytest.raises(ValueError):
        clear_customs_db(db, cu["cust_id"])
    dv = deliver_shipment_db(db, s2["ship_id"],
        at="2026-01-06")
    assert dv["status"] == "entregado"
    with pytest.raises(ValueError):
        deliver_shipment_db(db, s2["ship_id"])
    print("OK SUB logistica: nacionales sin aduana + internacionales con aduana obligatoria (regla 59) y entrega bloqueada hasta despacho + tarifas 2d")


def test_radar_vip_alertas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "r.db")
    e6(db)
    w1 = watch_db(db, buyer="VIP-1",
        category="inmuebles", min_value=100000.0,
        created_at="2026")
    w2 = watch_db(db, buyer="VIP-2",
        category="inmuebles", min_value=500000.0,
        created_at="2026")
    with pytest.raises(ValueError):
        watch_db(db, buyer=" ", category="X")
    p = publish_offer_db(db, category="inmuebles",
        ref="OFERTA-1", value=200000.0,
        detail="casa colonial",
        created_at="2026-01-01")
    assert p["alerts_fired"] == 1
    assert p["buyers"] == ["VIP-1"]
    assert p["event"] == "radar.offer_alert"
    p2 = publish_offer_db(db, category="inmuebles",
        ref="OFERTA-2", value=600000.0,
        created_at="2026-01-02")
    assert p2["alerts_fired"] == 2
    al = alerts_of_db(db, "VIP-1")
    assert len(al) == 2
    un = unwatch_db(db, w2["watch_id"])
    assert un["removed"] is True
    with pytest.raises(KeyError):
        unwatch_db(db, w2["watch_id"])
    print("OK SUB radar: seguimiento por categoria+min_value + alertas solo a calificados + evento radar.offer_alert para el cartero (NUNCA punto a punto) + baja de seguimiento")
