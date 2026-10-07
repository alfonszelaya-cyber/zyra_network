import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore

TUT = [{"name": "Mama", "relation": "MADRE", "zid": "ZID-M-1"}]
PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]

def _store(tmp_path):
    db = SQLiteAdapter(tmp_path / "w.db")
    st = SemillaStore(db, FrozenClock())
    return db, st

def test_store_autowire_y_pending(tmp_path) -> None:
    db, st = _store(tmp_path)
    assert st.canonical_bridge is not None
    row = st.add_account(account_id="ACC-1", zid="ZID-A1",
        name="Alumno Uno", role="alumno",
        school="INST-1", grade="primaria")
    assert row["account_id"] == "ACC-1"
    pend = st.canonical_bridge.pending_list()
    assert len(pend) == 1
    assert "SE-3" in str(pend[0]["reason"])
    print("OK autowire REAL: el store del server vivo queda conectado al canonico; alta sin datos SE-3 -> cola honesta (regla 66)")

def test_viejo_intacto_lookuperror(tmp_path) -> None:
    db, st = _store(tmp_path)
    st.add_account(account_id="P-1", zid=None,
        name="Profe Ruiz", role="profesor",
        school="INST-1", grade=None)
    with pytest.raises(LookupError):
        st.get_account("NO-EXISTE")
    prof = st.get_account("P-1")
    assert prof["role"] == "profesor"
    assert len(st.canonical_bridge.pending_list()) == 0
    print("OK viejo intacto: LookupError preservado, profesor NO se espeja al canonico")

def test_complete_pending_a_canonico(tmp_path) -> None:
    db, st = _store(tmp_path)
    st.add_account(account_id="ACC-2", zid="ZID-A2",
        name="Alumno Dos", role="alumno",
        school="INST-1", grade="primaria")
    est = st.canonical_bridge.complete_pending(
        "ACC-2", tutores=TUT,
        authorized_pickup=PICK2,
        emergency_contacts=EMG)
    assert est["zid"] == "ZID-A2"
    assert st.canonical_bridge.pending_list() == []
    row = db.query_one(
        "SELECT student_id FROM sm_legacy_map"
        " WHERE account_id = ?", ("ACC-2",))
    assert row is not None
    got = st.get_account("ACC-2")
    assert got["account_id"] == "ACC-2"
    print("OK complete_pending: cola -> expediente canonico SE-3 completo + mapa; lectura viejo-primero")

def test_fallback_canonico_real(tmp_path) -> None:
    db, st = _store(tmp_path)
    st.add_account(account_id="ACC-3", zid="ZID-A3",
        name="Alumno Tres", role="alumno",
        school="INST-1", grade="primaria")
    st.canonical_bridge.complete_pending(
        "ACC-3", tutores=TUT,
        authorized_pickup=PICK2,
        emergency_contacts=EMG)
    with db.transaction() as cursor:
        cursor.execute(
            "DELETE FROM semilla_accounts"
            " WHERE account_id = ?", ("ACC-3",))
    got = st.get_account("ACC-3")
    assert got.get("canonico") is True
    assert got["zid"] == "ZID-A3"
    print("OK fallback REAL: LookupError del viejo -> mapa -> canonico (con el store real, no solo Fake)")
