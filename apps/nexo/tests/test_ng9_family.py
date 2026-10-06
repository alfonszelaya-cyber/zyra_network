import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.family_office.real_estate_engine import RealEstateEngine
from apps.nexo.domain.family_office.metals_engine import MetalsEngine
from apps.nexo.domain.family_office.vehicles_engine import VehiclesEngine
from apps.nexo.domain.family_office.agricultural_land_engine import AgriculturalLandEngine
from apps.nexo.domain.family_office.art_engine import ArtEngine
from apps.nexo.domain.family_office.business_assets_engine import BusinessAssetsEngine
from apps.nexo.domain.family_office.collectibles_engine import CollectiblesEngine
from apps.nexo.domain.family_office.family_governance_engine import FamilyGovernanceEngine
from apps.nexo.domain.family_office.succession_engine import SuccessionEngine
from apps.nexo.application.family_office_use_cases.manage_real_estate_use_case import ManageRealEstateUseCase
from apps.nexo.application.family_office_use_cases.manage_metals_use_case import ManageMetalsUseCase
from apps.nexo.application.family_office_use_cases.family_governance_use_case import FamilyGovernanceUseCase
from apps.nexo.application.family_office_use_cases.succession_planning_use_case import SuccessionPlanningUseCase

def test_all_7_engines_instantiate(tmp_path) -> None:
    clock = FrozenClock()
    engines = [RealEstateEngine, MetalsEngine,
               VehiclesEngine, AgriculturalLandEngine,
               ArtEngine, BusinessAssetsEngine,
               CollectiblesEngine]
    for cls in engines:
        db = SQLiteAdapter(tmp_path / (cls.__name__
                                       + ".db"))
        eng = cls(db, clock)
        assert eng.list_for("EMP-X") == []
        assert eng.total_value("EMP-X") == "0.00"
    print("OK 7 engines FO: instancian y listan vacios")

def test_real_estate_decimal_lifecycle(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "re.db")
    eng = RealEstateEngine(db, FrozenClock())
    a = eng.register(company_id="EMP-FO",
        name="Casa SV", value="250000.5",
        property_type="CASA", location="San Salvador",
        area_m2="250")
    assert a["value"] == "250000.50"
    eng.register(company_id="EMP-FO", name="Apt",
        value="80000", property_type="APTO",
        location="Santa Tecla", area_m2="90")
    assert (eng.total_value("EMP-FO")
            == "330000.50")
    eng.update_value(a["asset_id"], "260000")
    assert (eng.total_value("EMP-FO")
            == "340000.00")
    b = eng.list_for("EMP-FO")[1]
    eng.deactivate(b["asset_id"])
    assert (eng.total_value("EMP-FO")
            == "260000.00")
    print("OK bienes raices: Decimal 2d + update + deactivate")

def test_metals_and_vehicles(tmp_path) -> None:
    m = MetalsEngine(SQLiteAdapter(tmp_path / "m.db"),
                     FrozenClock())
    m.register(company_id="EMP-FO", name="Lingote",
        value="65000", metal_type="ORO",
        weight_grams="1000", purity="0.999")
    m.register(company_id="EMP-FO", name="Plata",
        value="5000", metal_type="PLATA",
        weight_grams="5000", purity="0.925")
    assert m.total_value("EMP-FO") == "70000.00"
    v = VehiclesEngine(SQLiteAdapter(tmp_path / "v.db"),
                       FrozenClock())
    r = v.register(company_id="EMP-FO", name="Camion",
        value="35000.25", make="Toyota",
        model="Hilux", model_year="2024",
        plate="P-123-456")
    assert r["value"] == "35000.25"
    assert v.total_value("EMP-FO") == "35000.25"
    print("OK metales+vehiculos: inventario Decimal")

def test_usecases_manage_and_governance(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "uc.db")
    clock = FrozenClock()
    re_eng = RealEstateEngine(db, clock)
    uc = ManageRealEstateUseCase(re_eng)
    r = uc.execute(action="register",
        company_id="EMP-UC", name="Local",
        value="120000", property_type="LOCAL",
        location="Centro", area_m2="150")
    assert (r["registered"]["value"]
            == "120000.00")
    assert len(uc.execute(action="list",
        company_id="EMP-UC")["assets"]) == 1
    assert (uc.execute(action="total",
        company_id="EMP-UC")["total"]
        == "120000.00")
    assert "error" in uc.execute(action="xxx",
        company_id="EMP-UC")
    met = ManageMetalsUseCase(
        MetalsEngine(SQLiteAdapter(tmp_path / "m2.db"),
                     clock))
    met.execute(action="register",
        company_id="EMP-UC", name="Oro",
        value="1000", metal_type="ORO",
        weight_grams="10", purity="0.999")
    assert (met.execute(action="total",
        company_id="EMP-UC")["total"]
        == "1000.00")
    gov = FamilyGovernanceUseCase(
        FamilyGovernanceEngine(
            SQLiteAdapter(tmp_path / "g.db"), clock))
    d = gov.execute(action="register",
        subject="Venta de activo",
        participants=["Padre", "Hijo1"],
        resolution="Aprobada por unanimidad")
    assert (d["decision"]["status"] == "APPROVED")
    assert len(gov.execute(action="list")
               ["decisions"]) == 1
    suc = SuccessionPlanningUseCase(
        SuccessionEngine(
            SQLiteAdapter(tmp_path / "s.db"), clock))
    p = suc.execute(action="create",
        title="Plan Perez",
        successors=["Hijo1"], assets=["RE-1"])
    assert p["plan"]["status"] == "ACTIVE"
    assert len(suc.execute(action="list")
               ["plans"]) == 1
    print("OK use cases FO: manage + governance + sucesion")

def test_delegates_sin_duplicacion() -> None:
    from apps.nexo.application.family_office_use_cases.asset_valuation_use_case import (
        AssetValuationUseCase as FromSuffixed)
    from apps.nexo.application.family_office_use_cases.asset_valuation import (
        AssetValuationUseCase as Canonical)
    assert FromSuffixed is Canonical
    from apps.nexo.application.family_office_use_cases.create_trust_use_case import (
        CreateTrustUseCase as T1)
    from apps.nexo.application.family_office_use_cases.create_trust import (
        CreateTrustUseCase as T2)
    assert T1 is T2
    print("OK delegados: _use_case reexporta al canonico (cero duplicar)")
