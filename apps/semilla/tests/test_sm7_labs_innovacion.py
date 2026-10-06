import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.laboratory.laboratory_engine import LaboratoryEngine
from apps.semilla.domain.innovation.innovation_engine import InnovationEngine
from apps.semilla.domain.research.research_engine import ResearchEngine
from apps.semilla.domain.library.library_engine import LibraryEngine

def test_laboratorio_proyecto_experimentos(tmp_path) -> None:
    lab = LaboratoryEngine(
        SQLiteAdapter(tmp_path / "l.db"), FrozenClock())
    p = lab.create_project(lab_type="AI", title="Vision"
        " para clasificar residuos", lead_student_id="STU-1",
        members=["STU-2", "STU-3"])
    assert p["status"] == "ACTIVE"
    with pytest.raises(ValueError):
        lab.create_project(lab_type="COCINA", title="x",
            lead_student_id="STU-1")
    lab.run_experiment(project_id=p["project_id"],
        name="entrenar modelo v1", method="cnn",
        result="94% precision", success=True)
    lab.run_experiment(project_id=p["project_id"],
        name="entrenar modelo v2", method="transformer",
        result="97% precision", success=True)
    assert len(lab.experiments_of(p["project_id"])) == 2
    c = lab.complete_project(p["project_id"])
    assert c["status"] == "COMPLETED"
    with pytest.raises(ValueError):
        lab.run_experiment(project_id=p["project_id"],
            name="mas", method="x", result="y",
            success=True)
    assert len(lab.projects_by_lab("AI")) == 1
    print("OK laboratorio: proyecto->experimentos->cierre + lab_type validado")

def test_innovacion_startup_patente(tmp_path) -> None:
    inno = InnovationEngine(
        SQLiteAdapter(tmp_path / "i.db"), FrozenClock())
    s = inno.create_startup(name="AgroSense",
        founder_student_id="STU-5",
        description="sensores con IA")
    assert s["stage"] == "IDEA"
    s2 = inno.advance_stage(s["startup_id"])
    assert s2["stage"] == "INCUBATING"
    s3 = inno.advance_stage(s["startup_id"])
    assert s3["stage"] == "LAUNCHED"
    with pytest.raises(ValueError):
        inno.advance_stage(s["startup_id"])
    pat = inno.file_patent(title="Sensor humedad v2",
        student_id="STU-5", project_ref="SMLAB-1")
    assert pat["status"] == "FILED"
    upd = inno.update_patent(pat["patent_id"],
        status="GRANTED")
    assert upd["status"] == "GRANTED"
    with pytest.raises(ValueError):
        inno.update_patent(pat["patent_id"],
            status="GANYADOR")
    assert len(inno.startups_by_stage("LAUNCHED")) == 1
    with pytest.raises(ValueError):
        inno.create_startup(name="", founder_student_id="X")
    print("OK innovacion: startup IDEA->INCUBATING->LAUNCHED + patente FILED->GRANTED")

def test_investigacion_publicacion(tmp_path) -> None:
    res = ResearchEngine(
        SQLiteAdapter(tmp_path / "r.db"), FrozenClock())
    r = res.create_research(title="Impacto del tutor IA"
        " en matematica", lead_student_id="STU-7",
        area="EDUCACION", summary="estudio preliminar")
    assert r["status"] == "ACTIVE"
    pub = res.publish(r["research_id"],
        final_summary="mejora del 25% en retencion")
    assert pub["status"] == "PUBLISHED"
    with pytest.raises(ValueError):
        res.publish(r["research_id"])
    assert len(res.active_research()) == 0
    with pytest.raises(ValueError):
        res.create_research(title="", lead_student_id="X")
    print("OK investigacion: crear->publicar + estados")

def test_biblioteca_catalogo_prestamos(tmp_path) -> None:
    lib = LibraryEngine(SQLiteAdapter(tmp_path / "lib.db"),
                        FrozenClock())
    b = lib.add_book(title="Cien anos de soledad",
        author="Garcia Marquez", copies=2)
    assert b["copies_available"] == 2
    l1 = lib.checkout(book_id=b["book_id"],
        student_id="STU-8")
    lib.checkout(book_id=b["book_id"],
        student_id="STU-9")
    assert (lib.get_book(b["book_id"])
            ["copies_available"]) == 0
    with pytest.raises(ValueError):
        lib.checkout(book_id=b["book_id"],
            student_id="STU-10")
    lib.return_book(l1["loan_id"])
    assert (lib.get_book(b["book_id"])
            ["copies_available"]) == 1
    hits = lib.search("soledad")
    assert len(hits) == 1
    print("OK biblioteca: catalogo + prestamo/devolucion transaccional + busqueda")
