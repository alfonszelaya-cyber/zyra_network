import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.family_office.family_asset_engine import FamilyAssetEngine
from apps.nexo.domain.family_office.wealth_management_engine import WealthManagementEngine
from apps.nexo.domain.family_office.trust_management_engine import TrustManagementEngine
from apps.nexo.domain.family_office.inheritance_engine import InheritanceEngine
from apps.nexo.domain.family_office.succession_engine import SuccessionEngine
from apps.nexo.domain.family_office.world_heritage_engine import WorldHeritageEngine
from apps.nexo.application.family_office_use_cases.asset_valuation import AssetValuationUseCase
from apps.nexo.application.family_office_use_cases.world_heritage_management import WorldHeritageManagementUseCase

def test_assets_and_valuation(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fo.db")
    clock = FrozenClock()
    assets = FamilyAssetEngine(db, clock)
    assets.register_asset(asset_type="INMUEBLE", asset_name="Casa SV",
                          value="250000", jurisdiction="SV")
    assets.register_asset(asset_type="VEHICULO", asset_name="Camioneta",
                          value="35000", jurisdiction="SV")
    total = assets.calculate_total_assets()
    assert str(total) == "285000"
    wealth = WealthManagementEngine()
    snap = wealth.generate_wealth_snapshot(total_assets=total,
                                           total_liabilities="50000")
    assert snap["net_worth"] == "235000"
    uc = AssetValuationUseCase(assets, wealth)
    r = uc.execute(total_liabilities="50000")
    assert r["num_assets"] == 2
    print("OK family office: valoracion 285000, neto 235000")

def test_trust_inheritance_succession(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fo2.db")
    clock = FrozenClock()
    trust = TrustManagementEngine(db, clock)
    t = trust.create_trust(trust_name="Familia Perez", jurisdiction="SV",
                           beneficiaries=["Hijo1", "Hijo2"])
    assert t["status"] == "ACTIVE"
    inh = InheritanceEngine(db, clock)
    i = inh.create_inheritance(estate_name="Estado Perez",
                               beneficiaries=["Hijo1"], total_value="100000")
    assert i["status"] == "PLANNED"
    suc = SuccessionEngine(db, clock)
    pl = suc.create_plan(title="Plan Perez", successors=["Hijo1"],
                         assets=["AST-1"])
    assert pl["status"] == "ACTIVE"
    print("OK family office: trust + herencia + sucesion")

def test_world_heritage(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fo3.db")
    eng = WorldHeritageEngine(db, FrozenClock())
    eng.register_heritage_asset(asset_name="Sitio arqueologico",
                                asset_type="HISTORICO", country="SV",
                                estimated_value="50000")
    uc = WorldHeritageManagementUseCase(eng)
    s = uc.execute(action="summary")
    assert s["total_assets"] == 1
    assert s["total_value"] == "50000"
    print("OK family office: patrimonio mundial 50000")
