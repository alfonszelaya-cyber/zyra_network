import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.identity.consent_ledger_engine import ConsentLedgerEngine
from shared_engines.identity.presentation_engine import PresentationEngine
from shared_engines.identity.governance_engine import GovernanceEngine
from shared_engines.identity.assurance_engine import AssuranceEngine
from shared_engines.identity.federation_adapters_engine import FederationAdaptersEngine
from shared_engines.identity.oidc_bridge_engine import OidcBridgeEngine
from shared_engines.identity.mi_zid_engine import MiZidEngine
from shared_engines.identity.identity_gateways_engine import IdentityGatewaysEngine
from shared_engines.identity.tokens_engine import TokensEngine


def test_id3_consent_ledger(tmp_path):
    db = SQLiteAdapter(tmp_path / "cl.db")
    eng = ConsentLedgerEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.grant(zid=" ", purpose="salud")
    r = eng.grant(zid="ZID-1", purpose="salud.datos",
                  app="axis", scope=["lectura"])
    assert r["ok"] is True
    assert eng.check(zid="ZID-1",
        purpose="salud.datos",
        app="axis")["granted"] is True
    assert eng.check(zid="ZID-1",
        purpose="salud.datos",
        app="otro")["granted"] is False
    eng.revoke(zid="ZID-1", purpose="salud.datos",
               app="axis")
    assert eng.check(zid="ZID-1",
        purpose="salud.datos",
        app="axis")["granted"] is False
    with pytest.raises(ValueError):
        eng.revoke(zid="ZID-1",
            purpose="salud.datos", app="axis")
    eng.grant(zid="ZID-1", purpose="salud.datos",
        app="axis", expires_at=1.0)
    assert eng.check(zid="ZID-1",
        purpose="salud.datos",
        app="axis")["granted"] is False
    print("OK ID-3: ledger con hash-chain, grant/revoke/expiracion")


def test_id7_presentation(tmp_path):
    db = SQLiteAdapter(tmp_path / "p.db")
    eng = PresentationEngine(db, FrozenClock(),
        master_key="clave")
    with pytest.raises(ValueError):
        eng.present(zid=" ", fields={"a": 1})
    with pytest.raises(ValueError):
        eng.present(zid="ZID-1", fields={})
    p = eng.present(zid="ZID-1",
        fields={"nombre": "Ana", "edad": 25})
    assert len(p["seal"]) == 64
    v = eng.verify(p["pres_id"], zid="ZID-1",
        fields={"nombre": "Ana", "edad": 25},
        nonce=p["nonce"], seal=p["seal"])
    assert v["valid"] is True
    v2 = eng.verify(p["pres_id"], zid="ZID-1",
        fields={"nombre": "OTRA", "edad": 25},
        nonce=p["nonce"], seal=p["seal"])
    assert v2["valid"] is False
    assert "original" in v2["reason"]
    v3 = eng.verify(p["pres_id"], zid="ZID-1",
        fields={"nombre": "Ana", "edad": 25},
        nonce="OTRO-NONCE", seal=p["seal"])
    assert v3["valid"] is False
    assert "original" in v3["reason"]
    print("OK ID-7: selective disclosure — campos alterados y nonce distinto detectados vs original")


def test_id5_governance(tmp_path):
    db = SQLiteAdapter(tmp_path / "g.db")
    eng = GovernanceEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.create_policy(name=" ",
            rule={"denied_actions": []})
    with pytest.raises(ValueError):
        eng.create_policy(name="P1", rule={})
    p = eng.create_policy(name="Base",
        rule={"denied_actions": ["delete"]},
        created_by="GOB-1")
    with pytest.raises(ValueError):
        eng.decide(policy_id=p["policy_id"],
            subject_zid="ZID-1", action="noexiste",
            approve=True, reason="x")
    d = eng.decide(policy_id=p["policy_id"],
        subject_zid="ZID-1", action="verify",
        approve=True, decided_by="GOB-1",
        reason="solicitud valida")
    assert d["decision"] == "approved"
    assert len(eng.decisions_of("ZID-1")) == 1
    print("OK ID-5: politicas + decisiones")


def test_id1_assurance(tmp_path):
    db = SQLiteAdapter(tmp_path / "a.db")
    eng = AssuranceEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.compute(zid=" ")
    assert eng.compute(zid="ZID-1")["level"] == "L0"
    assert eng.compute(zid="ZID-1",
        has_active_zid=True,
        has_biometrics=True)["level"] == "L2"
    assert eng.compute(zid="ZID-1",
        has_active_zid=True, has_biometrics=True,
        has_official_doc=True)["level"] == "L3"
    assert eng.level_of("ZID-1")["level"] == "L3"
    assert eng.level_of("ZID-NADIE")[
        "level"] == "L0"
    print("OK ID-1: niveles L0..L3 por evidencia")


def test_id2_federation(tmp_path):
    db = SQLiteAdapter(tmp_path / "f.db")
    eng = FederationAdaptersEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.link_identity(zid=" ", provider="GOOGLE",
            external_id="E-1")
    with pytest.raises(ValueError):
        eng.link_identity(zid="ZID-1",
            provider="FACEBOOK", external_id="E-1")
    eng.link_identity(zid="ZID-1", provider="GOOGLE",
        external_id="GO-1")
    with pytest.raises(ValueError):
        eng.link_identity(zid="ZID-2",
            provider="GOOGLE", external_id="GO-1")
    assert eng.zid_of_external(provider="GOOGLE",
        external_id="GO-1")["zid"] == "ZID-1"
    assert eng.links_of("ZID-1") != []
    eng.unlink_identity(zid="ZID-1",
        provider="GOOGLE")
    assert eng.links_of("ZID-1") == []
    print("OK ID-2: federacion ZID<->externo + unlink")


def test_id10_oidc(tmp_path):
    db = SQLiteAdapter(tmp_path / "o.db")
    eng = OidcBridgeEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.issue_token(zid=" ", client_id="app",
            scopes=["openid"])
    with pytest.raises(ValueError):
        eng.issue_token(zid="ZID-1", client_id="app",
            scopes=["invalido"])
    t = eng.issue_token(zid="ZID-1",
        client_id="app-x",
        scopes=["openid", "profile"],
        ttl_seconds=100)
    assert t["expires_in"] == 100
    ins = eng.introspect(t["token"])
    assert ins["active"] is True
    assert ins["zid"] == "ZID-1"
    eng.revoke_token(t["token"])
    assert eng.introspect(t["token"])[
        "active"] is False
    with pytest.raises(ValueError):
        eng.revoke_token(t["token"])
    with pytest.raises(LookupError):
        eng.revoke_token("ZT-NADIE")
    print("OK ID-10: scopes OIDC + introspeccion + revocacion")


def test_id8_mi_zid(tmp_path):
    db = SQLiteAdapter(tmp_path / "m.db")
    eng = MiZidEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.portfolio(" ")
    p = eng.portfolio("ZID-SOLO")
    assert p["identity"] is None
    assert p["guardians"] == []
    print("OK ID-8: MI ZID vista agregada")


def test_id9_gateways(tmp_path):
    db = SQLiteAdapter(tmp_path / "gw.db")
    eng = IdentityGatewaysEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.register_gateway(name=" ",
            kind="APP_MOVIL")
    with pytest.raises(ValueError):
        eng.register_gateway(name="X",
            kind="SATELITE")
    g = eng.register_gateway(name="App ESC",
        kind="APP_MOVIL", owner_zid="ZID-ADMIN")
    assert g["status"] == "abierta"
    assert len(eng.gateways_of()) == 1
    c = eng.close_gateway(g["gw_id"])
    assert c["status"] == "cerrada"
    with pytest.raises(ValueError):
        eng.close_gateway(g["gw_id"])
    print("OK ID-9: gateways registro/cierre")


def test_id11_tokens(tmp_path):
    db = SQLiteAdapter(tmp_path / "tk.db")
    eng = TokensEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.issue_pair(zid=" ")
    pair = eng.issue_pair(zid="ZID-1",
        scopes=["read"])
    assert pair["access_token"]
    assert pair["refresh_token"]
    chk = eng.check_access(pair["access_token"])
    assert chk["valid"] is True
    assert chk["scopes"] == ["read"]
    r = eng.refresh(pair["refresh_token"])
    assert r["access_token"]
    with pytest.raises(ValueError):
        eng.refresh(pair["refresh_token"])
    assert eng.check_access("ZAT-nadie")[
        "valid"] is False
    rv = eng.revoke_all("ZID-1")
    assert rv["revoked"] >= 2
    assert eng.check_access(
        r["access_token"])["valid"] is False
    print("OK ID-11: access+refresh, reuso detectado, revoke_all")
