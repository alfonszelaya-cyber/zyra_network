import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.infrastructure.persistence.canonical_bridge import CanonicalBridge

TUT = [{"name": "Mama", "relation": "MADRE",
        "zid": "ZID-M-1"}]
PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO",
        "phone": "911"}]

class FakeOldStore:
    def __init__(self):
        self.accounts = {}
    def add_account(self, *, account_id, zid="",
                    name="", role="alumno",
                    school="", grade="1", **extra):
        acc = {"account_id": account_id, "zid": zid,
               "name": name, "role": role,
               "school": school, "grade": grade,
               "status": "ACTIVO"}
        self.accounts[account_id] = acc
        return dict(acc)
    def get_account(self, account_id):
        acc = self.accounts.get(account_id)
        return dict(acc) if acc else None

def _setup(tmp_path):
    db = SQLiteAdapter(tmp_path / "s.db")
    clock = FrozenClock()
    reg = StudentRegistryEngine(db, clock)
    store = FakeOldStore()
    bridge = CanonicalBridge(db, clock, reg)
    bridge.wire(store)
    return db, reg, store, bridge

def test_dual_write_se3_completo(tmp_path) -> None:
    db, reg, store, bridge = _setup(tmp_path)
    r = store.add_account(account_id="LEG-1",
        zid="ZID-L1", name="Nino Uno",
        school="INST-1", grade="3",
        tutores=TUT, authorized_pickup=PICK2,
        emergency_contacts=EMG)
    assert r["status"] == "ACTIVO"
    row = db.query_one(
        "SELECT student_id FROM sm_legacy_map"
        " WHERE account_id = ?", ("LEG-1",))
    assert row is not None
    est = reg.get(str(row["student_id"]))
    assert est is not None
    assert est["zid"] == "ZID-L1"
    print("OK dual-write: alta vieja intacta + expediente canonico con mapa LEG-1 -> sm_students")

def test_pending_cuando_se3_incompleto(tmp_path) -> None:
    db, reg, store, bridge = _setup(tmp_path)
    r = store.add_account(account_id="LEG-2",
        zid="ZID-L2", name="Nino Dos")
    assert r["status"] == "ACTIVO"
    pend = bridge.pending_list()
    assert len(pend) == 1
    assert "SE-3" in str(pend[0]["reason"])
    print("OK pending: sin datos SE-3 no se fabrica nada falso (regla 66) — cola legible para completar")

def test_read_fill_canonico(tmp_path) -> None:
    db, reg, store, bridge = _setup(tmp_path)
    store.add_account(account_id="LEG-9",
        zid="ZID-L9", name="Nino Map",
        school="INST-1", grade="2",
        tutores=TUT, authorized_pickup=PICK2,
        emergency_contacts=EMG)
    got_viejo = store.get_account("LEG-9")
    assert got_viejo.get("canonico") is None
    del store.accounts["LEG-9"]
    got = store.get_account("LEG-9")
    assert got is not None
    assert got.get("canonico") is True
    assert got["account_id"] == "LEG-9"
    assert got["zid"] == "ZID-L9"
    print("OK read-through: viejo-primero con forma compatible; si el viejo no lo tiene, responde el canonico")

def test_viejo_jamas_se_rompe(tmp_path) -> None:
    db, reg, store, bridge = _setup(tmp_path)
    class BoomReg:
        def register(self, **k):
            raise RuntimeError("boom canonico")
    store2 = FakeOldStore()
    b2 = CanonicalBridge(db, FrozenClock(), BoomReg())
    b2.wire(store2)
    r = store2.add_account(account_id="LEG-B",
        zid="Z", name="X", school="INST-1", grade="1",
        tutores=TUT, authorized_pickup=PICK2,
        emergency_contacts=EMG)
    assert r["status"] == "ACTIVO"
    print("OK fallback: fallo del lado canonico -> operacion vieja pura, sin excepcion al server")
