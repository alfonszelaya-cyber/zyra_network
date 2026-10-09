import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.identity.recovery_engine import ZidRecoveryEngine
from shared_engines.identity.trust_registry_engine import TrustRegistryEngine
from shared_engines.identity.vault_engine import ZidVaultEngine
from shared_engines.identity.trust_graph_engine import TrustGraphEngine


def test_id13_recovery(tmp_path):
    db = SQLiteAdapter(tmp_path / "r.db")
    eng = ZidRecoveryEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.issue_codes(zid=" ", count=1)
    with pytest.raises(ValueError):
        eng.issue_codes(zid="ZID-1", count=11)
    r = eng.issue_codes(zid="ZID-1", count=3)
    assert len(r["codes"]) == 3
    assert eng.valid_remaining("ZID-1") == 3
    ok = eng.recover(zid="ZID-1", code=r["codes"][0])
    assert ok["ok"] is True
    bad = eng.recover(zid="ZID-1", code=r["codes"][0])
    assert bad["ok"] is False
    assert eng.valid_remaining("ZID-1") == 2
    print("OK ID-13: codigos un solo uso hasheados (regla 63)")


def test_id6_trust_registry(tmp_path):
    db = SQLiteAdapter(tmp_path / "t.db")
    eng = TrustRegistryEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        eng.register(issuer_id=" ", name="X",
                     kind="GOBIERNO")
    with pytest.raises(ValueError):
        eng.register(issuer_id="I", name="X",
                     kind="ALIEN")
    eng.register(issuer_id="ISS-1", name="MINED",
                 kind="EDUCACION")
    with pytest.raises(ValueError):
        eng.register(issuer_id="ISS-1", name="dup",
                     kind="BANCO")
    assert eng.is_trusted("ISS-1") is True
    eng.revoke("ISS-1", reason="caso")
    assert eng.is_trusted("ISS-1") is False
    with pytest.raises(ValueError):
        eng.revoke("ISS-1", reason="x")
    print("OK ID-6: emisores, dup rechazada, revocacion")


def test_id4_vault(tmp_path):
    db = SQLiteAdapter(tmp_path / "v.db")
    eng = ZidVaultEngine(db, FrozenClock(),
        master_key="clave-maestra")
    with pytest.raises(ValueError):
        eng.store_secret(zid=" ", skey="k",
                         plaintext="v")
    with pytest.raises(ValueError):
        eng.store_secret(zid="ZID-1", skey="k",
                         plaintext=" ")
    eng.store_secret(zid="ZID-1", skey="pin",
        plaintext="secreto-123")
    r = eng.read_secret(zid="ZID-1", skey="pin")
    assert r["plaintext"] == "secreto-123"
    row = db.query_one(
        "SELECT sealed FROM zid_vault WHERE"
        " skey = 'pin'")
    assert "secreto-123" not in str(row["sealed"])
    eng.store_secret(zid="ZID-1", skey="pin",
        plaintext="nuevo")
    r2 = eng.read_secret(zid="ZID-1", skey="pin")
    assert r2["plaintext"] == "nuevo"
    eng.delete_secret(zid="ZID-1", skey="pin")
    assert eng.read_secret(zid="ZID-1",
        skey="pin")["found"] is False
    with pytest.raises(KeyError):
        eng.delete_secret(zid="ZID-1",
                          skey="noexiste")
    print("OK ID-4: sellado sin claro (regla 63) + update + delete")


def test_id14_trust_graph(tmp_path):
    db = SQLiteAdapter(tmp_path / "g.db")
    eng = TrustGraphEngine(db, FrozenClock())
    e1 = eng.add_entity(name="Sujeto A",
        zid="ZID-A")
    with pytest.raises(ValueError):
        eng.add_entity(name=" ", kind="person")
    e2 = eng.add_entity(name="Org B",
        kind="organization")
    e3 = eng.add_entity(name="Ent C")
    with pytest.raises(ValueError):
        eng.add_entity(name="X", kind="alien")
    with pytest.raises(LookupError):
        eng.link(src=e1["ent_id"], dst="NO")
    eng.link(src=e1["ent_id"], dst=e2["ent_id"],
        relation="opera", weight=80)
    with pytest.raises(ValueError):
        eng.link(src=e1["ent_id"],
            dst=e1["ent_id"])
    with pytest.raises(ValueError):
        eng.link(src=e1["ent_id"],
            dst=e2["ent_id"], weight=150)
    assert len(eng.neighbors(e1["ent_id"])) == 1
    p = eng.trust_path(src=e1["ent_id"],
        dst=e2["ent_id"])
    assert p["found"] is True
    s = eng.trust_score(e2["ent_id"])
    assert s["score"] == 80
    assert eng.trust_score(e3["ent_id"])[
        "score"] is None
    print("OK ID-14: entidades + vinculos con peso + BFS + score")
