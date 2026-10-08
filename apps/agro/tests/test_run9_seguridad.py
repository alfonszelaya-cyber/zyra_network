import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.agro.modules.seguridad.rbac_engine import (
    ensure_db, register_user_db, grant_db, check_db,
    open_session_db, session_ok_db, close_session_db,
    register_device_db, deactivate_device_db,
    issue_recovery_db, consume_recovery_db)
from apps.agro.events.zyra_bridge import (
    ensure_db as eb, publish_outbox_db, mark_sent_db,
    fail_outbox_db, retry_dead_db, ingest_inbox_db,
    process_inbox_db, fail_inbox_db, reconcile_db)


def test_a15_rbac_sesiones_dispositivos_recuperacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "s.db")
    ensure_db(db)
    with pytest.raises(ValueError):
        register_user_db(db, name="X", role="alien")
    with pytest.raises(ValueError):
        register_user_db(db, name="Prod",
            role="productor")
    p = register_user_db(db, name="Juan Perez",
        role="productor", zid="ZID-JUAN",
        created_at="2026")
    assert check_db(db, user_id=p["user_id"],
        resource="agro_productions",
        action="write")["allowed"] is False
    grant_db(db, user_id=p["user_id"],
        resource="agro_productions", action="write")
    assert check_db(db, user_id=p["user_id"],
        resource="agro_productions",
        action="read")["allowed"] is True
    assert check_db(db, user_id=p["user_id"],
        resource="agro_aid_requests",
        action="write")["allowed"] is False
    with pytest.raises(ValueError):
        grant_db(db, user_id=p["user_id"],
            resource="X", action="delete")
    with pytest.raises(ValueError):
        open_session_db(db, user_id=p["user_id"],
            ttl_seconds=0)
    s = open_session_db(db, user_id=p["user_id"],
        ttl_seconds=100.0, created_at="2026")
    assert session_ok_db(db, s["session_id"],
        now=50.0)["ok"] is True
    assert session_ok_db(db, s["session_id"],
        now=150.0)["ok"] is False
    close_session_db(db, s["session_id"], now=60.0)
    assert session_ok_db(db, s["session_id"],
        now=70.0)["ok"] is False
    with pytest.raises(ValueError):
        close_session_db(db, s["session_id"],
                         now=80.0)
    d = register_device_db(db, user_id=p["user_id"],
        label="celular juan", created_at="2026")
    deactivate_device_db(db, d["device_id"])
    with pytest.raises(ValueError):
        issue_recovery_db(db, user_id=p["user_id"],
            code="1234")
    rc = issue_recovery_db(db, user_id=p["user_id"],
        code="recuperacion-2026",
        created_at="2026")
    assert "no se guarda en claro" in rc["note"]
    assert consume_recovery_db(
        db, user_id=p["user_id"],
        code="recuperacion-2026")["ok"] is True
    assert consume_recovery_db(
        db, user_id=p["user_id"],
        code="recuperacion-2026")["ok"] is False
    print("OK A-15: RBAC jerarquia + sesiones TTL + dispositivos + recuperacion un solo uso con hash (regla 63)")


def test_a16_bridge_idempotencia_dlq(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "z.db")
    eb(db)
    e1 = publish_outbox_db(db,
        event_type="AGRO_COSECHA_LOTE",
        aggregate_id="LOT-1",
        payload={"kg": 850.0},
        idem_key="cosecha|LOT-1|2026-04-20",
        created_at="2026-04-20")
    assert e1["duplicated"] is False
    e2 = publish_outbox_db(db,
        event_type="AGRO_COSECHA_LOTE",
        idem_key="cosecha|LOT-1|2026-04-20")
    assert e2["duplicated"] is True
    assert e2["event_id"] == e1["event_id"]
    with pytest.raises(ValueError):
        publish_outbox_db(db, event_type="X",
            idem_key=" ")
    mark_sent_db(db, e1["event_id"],
        sent_at="2026")
    with pytest.raises(ValueError):
        fail_outbox_db(db, e1["event_id"])
    e3 = publish_outbox_db(db,
        event_type="AGRO_PLAGA_ALERTA",
        aggregate_id="ZONA-5",
        payload={"plaga": "langosta"},
        idem_key="plaga|ZONA-5|2026-04-21",
        created_at="2026-04-21")
    f1 = fail_outbox_db(db, e3["event_id"])
    assert f1["attempts"] == 1
    assert f1["status"] == "pendiente"
    f2 = fail_outbox_db(db, e3["event_id"])
    f3 = fail_outbox_db(db, e3["event_id"])
    assert f3["status"] == "dead"
    with pytest.raises(ValueError):
        fail_outbox_db(db, e3["event_id"])
    rec = retry_dead_db(db, e3["event_id"])
    assert rec["status"] == "pendiente"
    with pytest.raises(ValueError):
        retry_dead_db(db, e3["event_id"])
    i1 = ingest_inbox_db(db, source_app="nexo",
        event_type="NEXO_PAGO_CONFIRMADO",
        payload={"monto": 950.0},
        idem_key="nexo|pago|A1",
        created_at="2026-04-22")
    i2 = ingest_inbox_db(db, source_app="nexo",
        event_type="NEXO_PAGO_CONFIRMADO",
        idem_key="nexo|pago|A1")
    assert i2["duplicated"] is True
    process_inbox_db(db, i1["msg_id"], at="2026")
    with pytest.raises(ValueError):
        process_inbox_db(db, i1["msg_id"])
    with pytest.raises(ValueError):
        fail_inbox_db(db, i1["msg_id"])
    rec = reconcile_db(db)
    assert rec["outbox"].get("enviado", 0) == 1
    assert rec["inbox"].get("procesado", 0) == 1
    print("OK A-16: IDEMPOTENCIA (misma idem_key -> mismo event_id) + enviado no falla + DEAD TERMINAL hasta retry (fix DENTRO del engine) + inbox idempotente + reconciliacion")
