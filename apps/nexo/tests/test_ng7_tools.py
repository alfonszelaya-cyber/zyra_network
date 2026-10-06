import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.search.search_engine import NexoSearchEngine
from apps.nexo.domain.search.search_registry import NexoSearchRegistry
from apps.nexo.domain.workflow.workflow_engine import NexoWorkflowEngine
from apps.nexo.domain.workflow.workflow_state import assert_transition
from apps.nexo.domain.reports.report_engine import NexoReportEngine
from apps.nexo.domain.reports.report_registry import NexoReportRegistry
from apps.nexo.application.reports_use_cases.generate_report_use_case import GenerateReportUseCase
from apps.nexo.application.reports_use_cases.export_report_use_case import ExportReportUseCase
from apps.nexo.domain.analytics.analytics_engine import NexoAnalyticsEngine
from apps.nexo.domain.analytics.business_metrics_engine import NexoBusinessMetrics
from apps.nexo.application.analytics_use_cases.generate_analytics_use_case import GenerateAnalyticsUseCase
from apps.nexo.application.analytics_use_cases.analyze_business_metrics_use_case import AnalyzeBusinessMetricsUseCase
from apps.nexo.domain.synchronization.synchronization_engine import NexoSyncEngine
from apps.nexo.domain.synchronization.external_data_sync import NexoExternalSync

def test_search_index(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "se.db")
    se = NexoSearchEngine(db, FrozenClock())
    se.index(entity_ref="OP-1", title="Cobro alcaldia",
        content="operacion de cobro impuestos",
        entity_type="OPERATION", company_id="EMP-1")
    se.index(entity_ref="F-100", title="Factura venta",
        content="factura de venta servicios",
        entity_type="INVOICE", company_id="EMP-1")
    se.index(entity_ref="EMP-1", title="Empresa demo",
        entity_type="COMPANY")
    hits = se.search("cobro impuestos")
    assert len(hits) >= 1
    assert hits[0]["entity_ref"] == "OP-1"
    hits2 = se.search("venta", entity_type="INVOICE")
    assert len(hits2) == 1
    assert se.search("") == []
    reg = NexoSearchRegistry(db, FrozenClock())
    assert reg.total() == 3
    assert reg.counts_by_type().get("INVOICE") == 1
    assert se.remove("OP-1") == 1
    print("OK search: indexado + busqueda por terminos + registro")

def test_workflow(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "wf.db")
    wf = NexoWorkflowEngine(db, FrozenClock())
    w = wf.create_workflow(name="Cierre contable",
        steps=["preparar", "revisar", "aprobar"])
    with pytest.raises(ValueError):
        wf.create_workflow(name="mal",
            steps=["a", "a"])
    run = wf.start_run(workflow_id=w["workflow_id"],
        payload={"period": "2026-03"})
    rid = run["run_id"]
    assert run["status"] == "CREATED"
    with pytest.raises(ValueError):
        wf.advance(rid)
    wf.start(rid)
    r1 = wf.advance(rid)
    assert r1["current_step_name"] == "revisar"
    wf.pause(rid)
    with pytest.raises(ValueError):
        wf.advance(rid)
    wf.resume(rid)
    r3 = wf.advance(rid)
    assert r3["status"] == "RUNNING"
    r4 = wf.advance(rid)
    assert r4["status"] == "COMPLETED"
    with pytest.raises(ValueError):
        wf.advance(rid)
    assert len(wf.runs_of(w["workflow_id"])) == 1
    with pytest.raises(ValueError):
        assert_transition("COMPLETED", "RUNNING")
    print("OK workflow: pasos + estados estrictos + pausa")

def test_reports(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "rp.db")
    eng = NexoReportEngine(db, FrozenClock())
    uc = GenerateReportUseCase(eng)
    r = uc.execute(report_type="MONTHLY_CLOSE",
        company_id="EMP-1", period="2026-03",
        data={"ingresos": "1000",
              "gastos": "300"})
    assert r["report_id"].startswith("RPT-")
    with pytest.raises(ValueError):
        uc.execute(report_type="", data={"a": 1})
    with pytest.raises(ValueError):
        uc.execute(report_type="X", data=None)
    ex = ExportReportUseCase(eng).execute(
        report_id=r["report_id"], fmt="text")
    assert "MONTHLY_CLOSE" in ex["content"]
    assert "ingresos: 1000" in ex["content"]
    exj = ExportReportUseCase(eng).execute(
        report_id=r["report_id"])
    assert exj["format"] == "json"
    reg = NexoReportRegistry(db, FrozenClock())
    assert reg.total() == 1
    print("OK reports: generar + exportar texto/json + registro")

def test_analytics(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "an.db")
    eng = NexoAnalyticsEngine(db, FrozenClock())
    uc = GenerateAnalyticsUseCase(eng)
    r = uc.execute(company_id="EMP-1",
        period="2026-03",
        records=[{"type": "INCOME",
                  "amount": "2000"},
                 {"type": "EXPENSE",
                  "amount": "700"},
                 {"type": "INCOME",
                  "amount": "500"}])
    assert r["metrics"]["total_income"] == "2500.00"
    assert r["metrics"]["total_expense"] == "700.00"
    assert r["metrics"]["net"] == "1800.00"
    assert r["metrics"]["record_count"] == "3"
    assert len(eng.history("EMP-1",
                           "2026-03")) == 4
    bm = NexoBusinessMetrics()
    s = AnalyzeBusinessMetricsUseCase(bm).execute(
        current_income="2500",
        current_expense="700",
        previous_income="2000")
    assert s["growth_pct"] == 25.0
    assert s["margin_pct"] == 72.0
    print("OK analytics: agregados 2d + KPIs crecimiento/margen")

def test_sync(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "sy.db")
    eng = NexoSyncEngine(db, FrozenClock())
    s1 = eng.start_sync("openmeteo")
    with pytest.raises(ValueError):
        eng.complete(s1["sync_id"], -1)
    with pytest.raises(KeyError):
        eng.complete("SYN-NOEXISTE", 1)
    c = eng.complete(s1["sync_id"], items_synced=7,
        detail="ok")
    assert c["status"] == "COMPLETED"
    assert c["items_synced"] == 7
    with pytest.raises(ValueError):
        eng.complete(s1["sync_id"], 99)
    s2 = eng.start_sync("marn")
    f = eng.fail(s2["sync_id"], detail="fuente caida")
    assert f["status"] == "FAILED"
    assert eng.last_sync("openmeteo")["status"] == "COMPLETED"
    assert eng.last_sync("noexiste") is None
    ext = NexoExternalSync()
    assert ext.mode == "not_configured"
    r = ext.sweep("openmeteo")
    assert r["status"] == "not_configured"
    class FakeClient:
        def sweep(self, source):
            return {"source": source, "items": 3}
    ext2 = NexoExternalSync(client=FakeClient())
    r2 = ext2.sweep("marn")
    assert r2["status"] == "ok"
    print("OK sync: corridas + rechazo negativos/doble cierre + KeyError inexistente")
