import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.audit.chain import AuditTrail
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.clients.client_engine import ClientEngine
from apps.nexo.domain.clients.client_history_engine import ClientHistoryEngine
from apps.nexo.domain.clients.client_registry import ClientRegistry
from apps.nexo.domain.clients.client_validation_engine import ClientValidationEngine
from apps.nexo.domain.clients.client_segmentation_engine import ClientSegmentationEngine
from apps.nexo.application.clients_use_cases.create_client_use_case import CreateClientUseCase
from apps.nexo.application.clients_use_cases.segment_client_use_case import SegmentClientUseCase
from apps.nexo.application.clients_use_cases.validate_client_use_case import ValidateClientUseCase
from apps.nexo.application.clients_use_cases.update_client_use_case import UpdateClientUseCase


def _db(tmp_path):
    return SQLiteAdapter(tmp_path / "cli.db")


def test_client_engine_crud(tmp_path) -> None:
    db = _db(tmp_path)
    eng = ClientEngine(db, FrozenClock())
    c = eng.create_client(name="Pedro SV", document="12345678-9", email="pedro@sv.com")
    assert c["status"] == "ACTIVE"
    u = eng.update_client(c["client_id"], {"email": "nuevo@sv.com"})
    assert u["email"] == "nuevo@sv.com"
    b = eng.block_client(c["client_id"])
    assert b["status"] == "BLOCKED"
    a = eng.activate_client(c["client_id"])
    assert a["status"] == "ACTIVE"
    s = eng.generate_summary()
    assert s["total_clients"] == 1
    print("OK clients: engine CRUD")


def test_registry_and_use_cases(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    reg = ClientRegistry(db, clock)
    uc_create = CreateClientUseCase(reg, audit)
    c = uc_create.execute(name="Juan", email="juan@sv.com", created_by="nexo")
    assert c["client_id"].startswith("CLI-"), str(c)
    got = reg.get_by_id(c["client_id"])
    assert got["name"] == "Juan"
    uc_update = UpdateClientUseCase(reg, audit)
    u = uc_update.execute(client_id=c["client_id"], updates={"phone": "7000-1234"})
    assert u["phone"] == "7000-1234"
    uc_seg = SegmentClientUseCase(reg)
    r = uc_seg.execute(client_id=c["client_id"])
    assert r["segment"] == "STANDARD"
    print("OK clients: registry + use cases con audit")


def test_validation(tmp_path) -> None:
    db = _db(tmp_path)
    val = ClientValidationEngine(db, FrozenClock())
    assert val.validate({"name": "Pedro", "document": "12345678", "email": "p@sv.com"}) is True
    assert val.validate({"name": "Pedro", "document": "12", "email": "mal"}) is False
    print("OK clients: validacion")


def test_history_and_segmentation(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    hist = ClientHistoryEngine(db, clock)
    hist.register_financial_event("CLI-1", {"amount": 100})
    hist.register_risk_event("CLI-1", {"level": "MEDIUM"})
    s = hist.generate_summary("CLI-1")
    assert s["financial_events"] == 1
    seg = ClientSegmentationEngine()
    assert seg.segment(20000000) == "CORPORATE"
    assert seg.vip_segment(95, 2000000) == "VIP"
    print("OK clients: historial + segmentacion")
