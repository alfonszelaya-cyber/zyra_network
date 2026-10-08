
"""Export Docs Engine (A-12): expediente completo de
exportacion sobre exportacion existente — expediente
(con lote exportable OPCIONAL verificado contra
agro_harvest_lots), documentos (PHYTO/CO/PACKING/
OTHER), despacho (carrier/contenedor). Estados:
open->ready->dispatched (regla 66).
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_harvest_lots ("
    " lot_id TEXT PRIMARY KEY, harvest_id TEXT NOT"
    " NULL, weight REAL NOT NULL, grade TEXT NOT"
    " NULL DEFAULT '', rejected REAL NOT NULL"
    " DEFAULT 0, storage TEXT NOT NULL DEFAULT '',"
    " created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_export_files ("
    " exp_id TEXT PRIMARY KEY, producer_id TEXT NOT"
    " NULL, destination TEXT NOT NULL, lot_id TEXT"
    " NOT NULL DEFAULT '', product TEXT NOT NULL"
    " DEFAULT '', quantity REAL NOT NULL DEFAULT 0,"
    " status TEXT NOT NULL DEFAULT 'open',"
    " created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_export_docs ("
    " doc_id TEXT PRIMARY KEY, exp_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, ref TEXT NOT NULL"
    " DEFAULT '', issued_at TEXT)",
    "CREATE TABLE IF NOT EXISTS"
    " agro_export_dispatch (dispatch_id TEXT"
    " PRIMARY KEY, exp_id TEXT NOT NULL, carrier"
    " TEXT NOT NULL, container TEXT NOT NULL"
    " DEFAULT '', dispatched_at TEXT)",
)
_DOCS = ("PHYTO", "CO", "PACKING", "OTHER")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def open_file_db(db, *, producer_id, destination,
                 product="", quantity=0.0,
                 lot_id="", created_at=""):
    ensure_db(db)
    if str(lot_id).strip():
        lot = db.query_one(
            "SELECT lot_id FROM"
            " agro_harvest_lots WHERE lot_id = ?",
            (str(lot_id),))
        if lot is None:
            raise LookupError(
                "lote no encontrado: "
                + str(lot_id))
    eid = "EXP-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_export_files (exp_id,"
        " producer_id, destination, lot_id, product,"
        " quantity, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
        (eid, str(producer_id), str(destination),
         str(lot_id), str(product),
         float(quantity or 0), str(created_at)))
    return {"exp_id": eid, "status": "open"}


def add_doc_db(db, *, exp_id, kind, ref="",
               issued_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_export_files WHERE"
        " exp_id = ?", (str(exp_id),))
    if row is None:
        raise LookupError(
            "expediente no encontrado: "
            + str(exp_id))
    if str(row["status"]) != "open":
        raise ValueError(
            "docs solo en expediente open")
    k = str(kind).upper()
    if k not in _DOCS:
        raise ValueError("kind debe ser "
                         + "/".join(_DOCS))
    did = "DOC-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_export_docs (doc_id,"
        " exp_id, kind, ref, issued_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (did, str(exp_id), k, str(ref),
         str(issued_at)))
    return {"doc_id": did, "kind": k}


def ready_db(db, exp_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_export_files WHERE"
        " exp_id = ?", (str(exp_id),))
    if row is None:
        raise KeyError(exp_id)
    if str(row["status"]) != "open":
        raise ValueError("estado: "
                         + str(row["status"]))
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM agro_export_docs"
        " WHERE exp_id = ?", (str(exp_id),))
    if int(n["n"]) < 2:
        raise ValueError(
            "listo requiere al menos 2"
            " documentos (regla 66)")
    db.execute(
        "UPDATE agro_export_files SET status ="
        " 'ready' WHERE exp_id = ?",
        (str(exp_id),))
    return {"exp_id": str(exp_id),
            "status": "ready"}


def dispatch_db(db, exp_id, *, carrier,
                container="", dispatched_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_export_files WHERE"
        " exp_id = ?", (str(exp_id),))
    if row is None:
        raise KeyError(exp_id)
    if str(row["status"]) != "ready":
        raise ValueError(
            "despacho requiere ready; estado: "
            + str(row["status"]))
    if not str(carrier).strip():
        raise ValueError("carrier requerido")
    did = "DSP-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_export_dispatch"
        " (dispatch_id, exp_id, carrier, container,"
        " dispatched_at) VALUES (?, ?, ?, ?, ?)",
        (did, str(exp_id), str(carrier),
         str(container), str(dispatched_at)))
    db.execute(
        "UPDATE agro_export_files SET status ="
        " 'dispatched' WHERE exp_id = ?",
        (str(exp_id),))
    return {"dispatch_id": did,
            "carrier": str(carrier),
            "status": "dispatched"}


def exports_of_db_full(db, producer_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT exp_id, destination, lot_id,"
        " product, quantity, status, created_at"
        " FROM agro_export_files WHERE producer_id"
        " = ? ORDER BY rowid",
        (str(producer_id),))
    out = []
    for r in rows:
        eid = str(r["exp_id"])
        docs = db.query_all(
            "SELECT kind, ref FROM"
            " agro_export_docs WHERE exp_id = ?"
            " ORDER BY rowid", (eid,))
        dsp = db.query_one(
            "SELECT carrier, container FROM"
            " agro_export_dispatch WHERE exp_id ="
            " ?", (eid,))
        out.append({"exp_id": eid,
                    "destination": str(
                        r["destination"]),
                    "lot_id": str(r["lot_id"]),
                    "product": str(r["product"]),
                    "quantity": float(
                        r["quantity"]),
                    "status": str(r["status"]),
                    "docs": [
                        {"kind": str(d["kind"]),
                         "ref": str(d["ref"])}
                        for d in docs],
                    "carrier": (str(
                        dsp["carrier"])
                        if dsp is not None
                        else "")})
    return out
