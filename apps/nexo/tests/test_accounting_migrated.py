
import pytest
from decimal import Decimal
from shared_engines.common.clocks import FrozenClock
from shared_engines.audit.chain import AuditTrail
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.accounting_engine import AccountingEngine
from apps.nexo.domain.accounting.journal_engine import JournalEngine
from apps.nexo.domain.accounting.balance_engine import BalanceEngine
from apps.nexo.domain.accounting.accounting_validation_engine import AccountingValidationEngine
from apps.nexo.domain.accounting.accounting_registry import AccountingRegistry
from apps.nexo.domain.accounting.reconciliation_engine import ReconciliationEngine


def _db(tmp_path):
    return SQLiteAdapter(tmp_path / "acc.db")


def test_create_entry_decimal(tmp_path) -> None:
    db = _db(tmp_path)
    eng = AccountingEngine(
        db, FrozenClock(),
        audit=AuditTrail(db, FrozenClock()))
    e = eng.create_entry(
        account_code="1101",
        amount="100.00",
        entry_type="DEBIT",
        description="venta")
    assert e["amount"] == "100.00"
    assert e["status"] == "POSTED"
    bal = eng.calculate_account_balance("1101")
    assert bal == Decimal("100.00")
    print("OK: asiento Decimal creado y balanceado")


def test_double_entry_journal_balance(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    eng = AccountingEngine(
        db, clock,
        audit=AuditTrail(db, clock))
    jrn = JournalEngine(
        db, clock,
        outbox=Outbox(db, clock))
    bal = BalanceEngine(db, clock)
    d = eng.create_entry(
        account_code="1101",
        amount="500.00",
        entry_type="DEBIT",
        description="cobro")
    c = eng.create_entry(
        account_code="4001",
        amount="500.00",
        entry_type="CREDIT",
        description="venta")
    jrn.register_entry(d)
    jrn.register_entry(c)
    b = bal.calculate_balance([d, c])
    assert Decimal(
        b["net_balance"]) == Decimal("0")
    assert Decimal(
        b["total_debits"]) == Decimal(
        b["total_credits"])
    print("OK: partida doble DEBIT=CREDIT neto 0")


def test_validation_and_registry(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    val = AccountingValidationEngine(db, clock)
    v = val.validate_entry({
        "account_code": "AB",
        "amount": -5,
        "entry_type": "X"})
    assert v["valid"] is False
    assert len(v["errors"]) == 3
    reg = AccountingRegistry(db, clock)
    reg.register({
        "entry_id": "ACC-1",
        "account_code": "1101",
        "amount": "50"})
    assert reg.total_entries() == 1
    assert reg.get_by_account("1101")
    up = reg.update(
        "ACC-1", {"status": "REVERSED"})
    assert up["status"] == "REVERSED"
    assert reg.delete("ACC-1") is True
    assert reg.total_entries() == 0
    print("OK: validacion + registry CRUD")


def test_reconciliation_match(tmp_path) -> None:
    db = _db(tmp_path)
    rec = ReconciliationEngine(
        db, FrozenClock())
    internos = [
        {"id": "P1", "amount": "100"},
        {"id": "P2", "amount": "200"}]
    banco = [{"id": "P1", "amount": "100"}]
    r = rec.reconcile(internos, banco)
    assert r["matched"] == 1
    assert r["missing_in_bank"] == 1
    assert r["missing_in_internal"] == 0
    assert r["status"] == "DIFFERENCES_FOUND"
    print("OK: conciliacion detecta diferencias")
