import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.axis.life_history.biometric_registry import (
    ensure_db as e16, register_device_db, enroll_db,
    verify_identity, identify_db, revoke_bio_db,
    biometrics_of_db)
from apps.axis.life_history.notify_center import (
    ensure_db as e18n, send_db, send_emergency_db,
    inbox_of_db, mark_read_db, critical_pending_db)
from apps.axis.life_history.certificate_issuer import (
    ensure_db as e18c, issue_db, verify_db,
    revoke_cert_db, certs_of_db)


def test_ax16_biometria_mismo_zid(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "b.db")
    e16(db)
    dev = register_device_db(db,
        device_id="DEV-HU-1", kind="HUELLA",
        location="REGISTRO-SS", created_at="2026")
    assert dev["device_id"] == "DEV-HU-1"
    with pytest.raises(ValueError):
        register_device_db(db, device_id="DEV-HU-1",
            kind="HUELLA")
    with pytest.raises(ValueError):
        register_device_db(db, device_id="DEV-2",
            kind="RETINA")
    en = enroll_db(db, person_id="P-1",
        zid="ZID-1", kind="HUELLA",
        template_b64="TEMPLATE-V1",
        device_id="DEV-HU-1", quality=85,
        at="2026-01-01")
    assert len(en["template_hash"]) == 64
    with pytest.raises(ValueError):
        enroll_db(db, person_id=" ",
            kind="HUELLA",
            template_b64="T")
    with pytest.raises(ValueError):
        enroll_db(db, person_id="P-1",
            kind="PALMILLA",
            template_b64="T")
    v = verify_identity(db, person_id="P-1",
        kind="HUELLA",
        template_b64="TEMPLATE-V1")
    assert v["matched"] is True
    v2 = verify_identity(db, person_id="P-1",
        kind="HUELLA",
        template_b64="TEMPLATE-OTRA")
    assert v2["matched"] is False
    idn = identify_db(db, kind="HUELLA",
        template_b64="TEMPLATE-V1")
    assert idn["matched"] is True
    assert idn["zid"] == "ZID-1"
    idn2 = identify_db(db, kind="ROSTRO",
        template_b64="TEMPLATE-V1")
    assert idn2["matched"] is False
    en2 = enroll_db(db, person_id="P-1",
        zid="ZID-1", kind="HUELLA",
        template_b64="TEMPLATE-V2",
        at="2026-06-01")
    bios = biometrics_of_db(db, "P-1")
    st = {b["bio_id"]: b["status"]
          for b in bios}
    assert st[en["bio_id"]] == "reemplazada"
    assert st[en2["bio_id"]] == "activa"
    rv = revoke_bio_db(db, en2["bio_id"],
        reason="datos corruptos",
        at="2026-07-01")
    assert rv["status"] == "revocada"
    with pytest.raises(ValueError):
        revoke_bio_db(db, en2["bio_id"])
    v3 = verify_identity(db, person_id="P-1",
        kind="HUELLA",
        template_b64="TEMPLATE-V2")
    assert v3["matched"] is False
    assert "sin plantilla" in v3["reason"]
    print("OK AX-16: dispositivo + enrolamiento MISMO ZID (regla 78) hash template (regla 63) + 1:1 + 1:N + reemplazo + revocacion (revoke_bio_db con alias)")


def test_ax18_notificaciones_y_certificados(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "n.db")
    e18n(db)
    e18c(db)
    n = send_db(db, channel="EMAIL",
        target_kind="ROL", target="DIRECTORES",
        subject="corte de servicio",
        priority="MEDIA", at="2026-01-01")
    assert n["priority"] == "MEDIA"
    with pytest.raises(ValueError):
        send_db(db, channel="PALOMA",
            target_kind="ROL", target="X",
            subject="Y")
    with pytest.raises(ValueError):
        send_db(db, channel="SMS",
            target_kind="ROL", target=" ",
            subject="Y")
    em = send_emergency_db(db, target="ZONA-5",
        subject="SISMO 6.2",
        at="2026-01-02")
    assert em["priority"] == "CRITICA"
    inbox = inbox_of_db(db, "DIRECTORES")
    assert len(inbox) == 1
    assert inbox[0]["read"] == ""
    zone = inbox_of_db(db, "ZONA-5",
                       unread_only=True)
    assert len(zone) == 1
    mk = mark_read_db(db, inbox[0]["notif_id"],
        at="2026-01-03")
    assert mk["read"] is True
    with pytest.raises(ValueError):
        mark_read_db(db, inbox[0]["notif_id"])
    crit = critical_pending_db(db)
    assert len(crit) == 1
    assert crit[0]["subject"] == "SISMO 6.2"
    c = issue_db(db, person_id="P-1", kind="CIVIL",
        payload="acta de nacimiento copia",
        zid="ZID-1", at="2026-01-01")
    assert c["cert_code"].startswith("CERT-")
    with pytest.raises(ValueError):
        issue_db(db, person_id="P-1",
            kind="ESPACIAL", payload="x")
    with pytest.raises(ValueError):
        issue_db(db, person_id="P-1", kind="CIVIL",
            payload=" ")
    vf = verify_db(db, c["cert_code"])
    assert vf["found"] is True
    assert vf["status"] == "VIGENTE"
    rv = revoke_cert_db(db, c["cert_code"],
        reason="duplicado detectado")
    assert rv["status"] == "REVOCADO"
    vf2 = verify_db(db, c["cert_code"])
    assert vf2["status"] == "REVOCADO"
    with pytest.raises(ValueError):
        revoke_cert_db(db, c["cert_code"],
            reason="otra vez")
    with pytest.raises(ValueError):
        revoke_cert_db(db, c["cert_code"],
            reason=" ")
    assert len(certs_of_db(db, "P-1")) == 1
    print("OK AX-18: notificaciones (canales/prioridades/bandeja/CRITICA) + certificados hash por titular (revoke_cert_db con alias)")
