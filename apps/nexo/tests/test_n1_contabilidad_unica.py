import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.accounting_engine import AccountingEngine
from apps.nexo.domain.accounting.journal_engine import JournalEngine


def _audit(tmp_path):
    from shared_engines.audit.chain import AuditTrail
    try:
        return AuditTrail(SQLiteAdapter(tmp_path / "aud.db"))
    except TypeError:
        try:
            return AuditTrail(db=SQLiteAdapter(tmp_path / "aud.db"))
        except Exception:
            class _D:
                def append(self, **kw):
                    return None
            return _D()


def _eng(tmp_path):
    return AccountingEngine(SQLiteAdapter(tmp_path / "a.db"),
                            FrozenClock(),
                            audit=_audit(tmp_path))


def test_balanced_aceptado(tmp_path) -> None:
    eng = _eng(tmp_path)
    r = eng.create_balanced_entry(lines=[
        {"account_code": "1000", "amount": "500",
         "entry_type": "DEBIT"},
        {"account_code": "4000", "amount": "500",
         "entry_type": "CREDIT"},
    ], description="venta al contado",
        reference_id="F-1")
    assert r["total"] == "500.00"
    assert r["lines"] == 2
    assert eng.calculate_account_balance(
        "1000") == pytest.approx(500.0)
    print("OK N-1: asiento cuadrado aceptado con group_id")


def test_descuadrado_rechazado(tmp_path) -> None:
    eng = _eng(tmp_path)
    with pytest.raises(ValueError):
        eng.create_balanced_entry(lines=[
            {"account_code": "1000", "amount": "500",
             "entry_type": "DEBIT"},
            {"account_code": "4000", "amount": "400",
             "entry_type": "CREDIT"},
        ], description="mal")
    with pytest.raises(ValueError):
        eng.create_balanced_entry(lines=[],
                                  description="vacio")
    with pytest.raises(ValueError):
        eng.create_balanced_entry(lines=[
            {"account_code": "1000", "amount": "10",
             "entry_type": "PIERNA"},
            {"account_code": "4000", "amount": "10",
             "entry_type": "CREDIT"},
        ], description="tipo malo")
    print("OK N-1: descuadrado/vacio/tipo-malo rechazados")


def test_pierna_individual_primitiva(tmp_path) -> None:
    eng = _eng(tmp_path)
    e = eng.create_entry(account_code="1000", amount="10",
        entry_type="DEBIT", description="pierna")
    assert e["status"] == "POSTED"
    print("OK N-1: create_entry sigue como primitiva de pierna")


def test_journal_valida_lines(tmp_path) -> None:
    j = JournalEngine(SQLiteAdapter(tmp_path / "j.db"),
                      FrozenClock())
    j.register_entry({"lines": [
        {"account_code": "1000", "amount": "100",
         "entry_type": "DEBIT"},
        {"account_code": "4000", "amount": "100",
         "entry_type": "CREDIT"},
    ]})
    with pytest.raises(ValueError):
        j.register_entry({"lines": [
            {"account_code": "1000", "amount": "100",
             "entry_type": "DEBIT"},
            {"account_code": "4000", "amount": "90",
             "entry_type": "CREDIT"},
        ]})
    j.register_entry({"account_code": "1000",
                      "amount": "5",
                      "entry_type": "DEBIT"})
    assert len(j.get_entries()) == 2
    print("OK journal: lines cuadradas exigidas + pierna suelta registrable")
