
"""Agronomy Engine (A-5): capas del ciclo agronomico
sobre planes existentes — insumos (semilla/
fertilizante/agroquimico con dosis), plagas con
tratamiento y cierre protegido, inspecciones,
resumen. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_plans ("
    " plan_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, unit_id TEXT NOT NULL, crop TEXT"
    " NOT NULL, target REAL NOT NULL, status TEXT"
    " NOT NULL, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_plan_inputs ("
    " input_id TEXT PRIMARY KEY, plan_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, product TEXT NOT"
    " NULL, dose REAL NOT NULL DEFAULT 0, unit"
    " TEXT NOT NULL DEFAULT '', applied_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_plan_pests ("
    " pest_id TEXT PRIMARY KEY, plan_id TEXT NOT"
    " NULL, pest_type TEXT NOT NULL, severity TEXT"
    " NOT NULL DEFAULT 'media', treatment TEXT NOT"
    " NULL DEFAULT '', reported_at TEXT, resolved"
    " INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS"
    " agro_plan_inspections (inspection_id TEXT"
    " PRIMARY KEY, plan_id TEXT NOT NULL, inspector"
    " TEXT NOT NULL, result TEXT NOT NULL, notes"
    " TEXT NOT NULL DEFAULT '', inspected_at"
    " TEXT)",
)
_KINDS = ("SEMILLA", "FERTILIZANTE",
          "AGROQUIMICO", "OTRO")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _plan(db, plan_id):
    row = db.query_one(
        "SELECT plan_id, crop, status FROM"
        " agro_plans WHERE plan_id = ?",
        (str(plan_id),))
    if row is None:
        raise LookupError(
            "plan no encontrado: "
            + str(plan_id))
    return row


def add_input_db(db, *, plan_id, kind, product,
                 dose=0.0, unit="", applied_at=""):
    ensure_db(db)
    _plan(db, plan_id)
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if float(dose) < 0:
        raise ValueError("dose no negativa")
    iid = "AGIN-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_plan_inputs (input_id,"
        " plan_id, kind, product, dose, unit,"
        " applied_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (iid, str(plan_id), k, str(product),
         float(dose), str(unit),
         str(applied_at)))
    return {"input_id": iid, "kind": k,
            "product": str(product),
            "dose": float(dose),
            "unit": str(unit)}


def inputs_of_db(db, plan_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT input_id, kind, product, dose,"
        " unit, applied_at FROM agro_plan_inputs"
        " WHERE plan_id = ? ORDER BY rowid",
        (str(plan_id),))
    return [{"input_id": str(r["input_id"]),
             "kind": str(r["kind"]),
             "product": str(r["product"]),
             "dose": float(r["dose"]),
             "unit": str(r["unit"]),
             "applied_at": str(
                 r["applied_at"])}
            for r in rows]


def report_pest_db(db, *, plan_id, pest_type,
                   severity="media",
                   treatment="",
                   reported_at=""):
    ensure_db(db)
    _plan(db, plan_id)
    pid = "AGPL-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_plan_pests (pest_id,"
        " plan_id, pest_type, severity, treatment,"
        " reported_at, resolved) VALUES (?, ?, ?,"
        " ?, ?, ?, 0)",
        (pid, str(plan_id), str(pest_type),
         str(severity), str(treatment),
         str(reported_at)))
    return {"pest_id": pid,
            "pest_type": str(pest_type),
            "severity": str(severity),
            "resolved": False}


def resolve_pest_db(db, pest_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT resolved FROM agro_plan_pests"
        " WHERE pest_id = ?", (str(pest_id),))
    if row is None:
        raise KeyError(pest_id)
    if int(row["resolved"]) == 1:
        raise ValueError("plaga ya resuelta")
    db.execute(
        "UPDATE agro_plan_pests SET resolved = 1"
        " WHERE pest_id = ?", (str(pest_id),))
    return {"pest_id": str(pest_id),
            "resolved": True}


def pests_of_db(db, plan_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT pest_id, pest_type, severity,"
        " treatment, reported_at, resolved FROM"
        " agro_plan_pests WHERE plan_id = ? ORDER"
        " BY rowid", (str(plan_id),))
    return [{"pest_id": str(r["pest_id"]),
             "pest_type": str(r["pest_type"]),
             "severity": str(r["severity"]),
             "treatment": str(r["treatment"]),
             "reported_at": str(
                 r["reported_at"]),
             "resolved": bool(
                 int(r["resolved"]))}
            for r in rows]


def add_inspection_db(db, *, plan_id, inspector,
                      result, notes="",
                      inspected_at=""):
    ensure_db(db)
    _plan(db, plan_id)
    if not str(result).strip():
        raise ValueError("result requerido")
    iid = "AGSP-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_plan_inspections"
        " (inspection_id, plan_id, inspector,"
        " result, notes, inspected_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (iid, str(plan_id), str(inspector),
         str(result), str(notes),
         str(inspected_at)))
    return {"inspection_id": iid,
            "inspector": str(inspector),
            "result": str(result)}


def inspections_of_db(db, plan_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT inspection_id, inspector, result,"
        " notes, inspected_at FROM"
        " agro_plan_inspections WHERE plan_id = ?"
        " ORDER BY rowid", (str(plan_id),))
    return [{"inspection_id": str(
                 r["inspection_id"]),
             "inspector": str(r["inspector"]),
             "result": str(r["result"]),
             "notes": str(r["notes"]),
             "inspected_at": str(
                 r["inspected_at"])}
            for r in rows]


def agronomic_summary_db(db, plan_id):
    ensure_db(db)
    row = _plan(db, plan_id)
    n_in = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " agro_plan_inputs WHERE plan_id = ?",
        (str(plan_id),))
    kinds = db.query_all(
        "SELECT kind, COUNT(*) AS n FROM"
        " agro_plan_inputs WHERE plan_id = ?"
        " GROUP BY kind", (str(plan_id),))
    n_open = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " agro_plan_pests WHERE plan_id = ? AND"
        " resolved = 0", (str(plan_id),))
    n_insp = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " agro_plan_inspections WHERE plan_id ="
        " ?", (str(plan_id),))
    return {"plan_id": str(plan_id),
            "crop": str(row["crop"]),
            "status": str(row["status"]),
            "inputs": int(n_in["n"]),
            "inputs_by_kind": {
                str(r["kind"]): int(r["n"])
                for r in kinds},
            "pests_open": int(n_open["n"]),
            "inspections": int(n_insp["n"])}
