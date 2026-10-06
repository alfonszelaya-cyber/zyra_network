import importlib, pathlib
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.government.government_registry import GovernmentRegistry

BASE = pathlib.Path(__file__).resolve().parents[1] / "domain" / "government"

def test_modulos_gobierno_importan():
    n = 0
    for p in sorted(BASE.glob("*.py")):
        if p.stat().st_size <= 1:
            continue
        importlib.import_module(
            "apps.nexo.domain.government." + p.stem)
        n = n + 1
    assert n >= 7
    print("OK government: " + str(n) + " modulos importan")

def test_presupuesto_publico_flujo(tmp_path):
    reg = GovernmentRegistry(
        SQLiteAdapter(tmp_path / "g.db"), FrozenClock())
    inst = reg.create_institution(name="Alcaldia",
        kind="MUNICIPALITY")
    prg = reg.create_program(
        institution_id=inst["institution_id"],
        name="Obras", period="2026", budgeted="10000")
    reg.commit_funds(program_id=prg["program_id"],
        amount="4000")
    reg.accrue(program_id=prg["program_id"],
        amount="3000")
    p = reg.pay(program_id=prg["program_id"],
        amount="2000")
    assert p["paid"] == "2000.00"
    print("OK government: presupuesto 4 fases")
