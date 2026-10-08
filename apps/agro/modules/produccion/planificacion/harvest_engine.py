
"""Harvest Engine (A-6): cosecha sobre planes
existentes (plan CANCELADO rechazado, regla 66) +
lotes con peso/grado/rechazos/almacen + trazabilidad
plan->cosecha->lote + carga por almacen.
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_plans ("
    " plan_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, unit_id TEXT NOT NULL, crop TEXT"
    " NOT NULL, target REAL NOT NULL, status TEXT"
    " NOT NULL, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_harvests ("
    " harvest_id TEXT PRIMARY KEY, plan_id TEXT"
    " NOT NULL, producer_id TEXT NOT NULL, product"
    " TEXT NOT NULL, quantity REAL NOT NULL, unit"
    " TEXT NOT NULL DEFAULT '', quality_grade TEXT"
    " NOT NULL DEFAULT '', losses REAL NOT NULL"
    " DEFAULT 0, note TEXT NOT NULL DEFAULT '',"
    " plan_status TEXT NOT NULL DEFAULT '',"
    " harvest_date TEXT)",
    "CREATE TABLE IF NOT EXISTS"
    " agro_harvest_lots (lot_id TEXT PRIMARY KEY,"
    " harvest_id TEXT NOT NULL, weight REAL NOT"
    " NULL, grade TEXT NOT NULL DEFAULT '',"
    " rejected REAL NOT NULL DEFAULT 0, storage"
    " TEXT NOT NULL DEFAULT '', created_at TEXT)",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_harvest_db(db, *, plan_id, quantity,
                        unit="", quality_grade="",
                        losses=0.0, note="",
                        harvest_date=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT producer_id, crop, status FROM"
        " agro_plans WHERE plan_id = ?",
        (str(plan_id),))
    if row is None:
        raise LookupError(
            "plan no encontrado: "
            + str(plan_id))
    if str(row["status"]) == "cancelled":
        raise ValueError(
            "no se cosecha un plan CANCELADO"
            " (regla 66)")
    if float(quantity) <= 0:
        raise ValueError("quantity positiva")
    if float(losses) < 0:
        raise ValueError("losses no negativas")
    hid = "HRV-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_harvests (harvest_id,"
        " plan_id, producer_id, product, quantity,"
        " unit, quality_grade, losses, note,"
        " plan_status, harvest_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (hid, str(plan_id),
         str(row["producer_id"]),
         str(row["crop"]), float(quantity),
         str(unit), str(quality_grade),
         float(losses), str(note),
         str(row["status"]),
         str(harvest_date)))
    return {"harvest_id": hid,
            "plan_id": str(plan_id),
            "producer_id": str(
                row["producer_id"]),
            "product": str(row["crop"]),
            "quantity": float(quantity),
            "quality_grade": str(quality_grade),
            "losses": float(losses)}


def add_lot_db(db, *, harvest_id, weight,
               grade="", rejected=0.0,
               storage="", created_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT harvest_id FROM agro_harvests"
        " WHERE harvest_id = ?",
        (str(harvest_id),))
    if row is None:
        raise LookupError(
            "cosecha no encontrada: "
            + str(harvest_id))
    if float(weight) <= 0:
        raise ValueError("weight positiva")
    if float(rejected) < 0:
        raise ValueError("rejected no negativo")
    lid = "LOT-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_harvest_lots (lot_id,"
        " harvest_id, weight, grade, rejected,"
        " storage, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lid, str(harvest_id), float(weight),
         str(grade), float(rejected),
         str(storage), str(created_at)))
    return {"lot_id": lid,
            "harvest_id": str(harvest_id),
            "weight": float(weight),
            "grade": str(grade),
            "rejected": float(rejected),
            "storage": str(storage)}


def lots_of_db(db, harvest_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT lot_id, weight, grade, rejected,"
        " storage, created_at FROM"
        " agro_harvest_lots WHERE harvest_id = ?"
        " ORDER BY rowid", (str(harvest_id),))
    return [{"lot_id": str(r["lot_id"]),
             "weight": float(r["weight"]),
             "grade": str(r["grade"]),
             "rejected": float(r["rejected"]),
             "storage": str(r["storage"]),
             "created_at": str(
                 r["created_at"])}
            for r in rows]


def harvests_of_db(db, producer_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT harvest_id, plan_id, product,"
        " quantity, unit, quality_grade, losses,"
        " harvest_date FROM agro_harvests WHERE"
        " producer_id = ? ORDER BY rowid",
        (str(producer_id),))
    return [{"harvest_id": str(r["harvest_id"]),
             "plan_id": str(r["plan_id"]),
             "product": str(r["product"]),
             "quantity": float(r["quantity"]),
             "unit": str(r["unit"]),
             "quality_grade": str(
                 r["quality_grade"]),
             "losses": float(r["losses"]),
             "harvest_date": str(
                 r["harvest_date"])}
            for r in rows]


def trace_of_lot_db(db, lot_id):
    ensure_db(db)
    lot = db.query_one(
        "SELECT lot_id, harvest_id, weight, grade,"
        " storage FROM agro_harvest_lots WHERE"
        " lot_id = ?", (str(lot_id),))
    if lot is None:
        raise LookupError(
            "lote no encontrado: " + str(lot_id))
    harv = db.query_one(
        "SELECT harvest_id, plan_id, producer_id,"
        " product, quantity, harvest_date FROM"
        " agro_harvests WHERE harvest_id = ?",
        (str(lot["harvest_id"]),))
    plan = None
    if harv is not None:
        plan = db.query_one(
            "SELECT plan_id, crop, status FROM"
            " agro_plans WHERE plan_id = ?",
            (str(harv["plan_id"]),))
    return {"lot": {"lot_id": str(lot["lot_id"]),
                    "weight": float(
                        lot["weight"]),
                    "grade": str(lot["grade"]),
                    "storage": str(
                        lot["storage"])},
            "harvest": (
                {"harvest_id": str(
                     harv["harvest_id"]),
                 "product": str(
                     harv["product"]),
                 "quantity": float(
                     harv["quantity"]),
                 "harvest_date": str(
                     harv["harvest_date"])}
                if harv is not None else None),
            "plan": (
                {"plan_id": str(
                     plan["plan_id"]),
                 "crop": str(plan["crop"]),
                 "status": str(plan["status"])}
                if plan is not None else None)}


def storage_load_db(db, storage):
    ensure_db(db)
    rows = db.query_all(
        "SELECT h.product AS product, SUM(hl"
        ".weight) AS total, SUM(hl.rejected) AS"
        " rejected FROM agro_harvest_lots hl JOIN"
        " agro_harvests h ON hl.harvest_id = h"
        ".harvest_id WHERE hl.storage = ? GROUP"
        " BY h.product ORDER BY h.product",
        (str(storage),))
    return {"storage": str(storage),
            "by_product": [
                {"product": str(r["product"]),
                 "weight": float(r["total"]
                                 or 0.0),
                 "rejected": float(
                     r["rejected"] or 0.0)}
                for r in rows]}
