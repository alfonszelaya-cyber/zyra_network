
"""Machinery Ops Engine (A-9): horas de uso,
combustible, mantenimiento preventivo/correctivo y
ordenes de trabajo sobre maquinaria existente
(agro_area_machinery, DDL confirmado). Resumen por
maquina. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_area_machinery"
    " (machine_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, machine_type TEXT NOT NULL,"
    " description TEXT, created_at REAL NOT NULL)",
    "CREATE TABLE IF NOT EXISTS agro_mach_usage ("
    " usage_id TEXT PRIMARY KEY, machine_id TEXT"
    " NOT NULL, hours REAL NOT NULL, fuel_liters"
    " REAL NOT NULL DEFAULT 0, operator TEXT NOT"
    " NULL DEFAULT '', logged_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_mach_maint ("
    " maint_id TEXT PRIMARY KEY, machine_id TEXT"
    " NOT NULL, kind TEXT NOT NULL, detail TEXT"
    " NOT NULL DEFAULT '', cost REAL NOT NULL"
    " DEFAULT 0, done_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_mach_orders ("
    " order_id TEXT PRIMARY KEY, machine_id TEXT"
    " NOT NULL, task TEXT NOT NULL, status TEXT"
    " NOT NULL DEFAULT 'open', opened_at TEXT,"
    " closed_at TEXT)",
)
_MAINT = ("PREVENTIVA", "CORRECTIVA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _machine(db, machine_id):
    row = db.query_one(
        "SELECT machine_id FROM"
        " agro_area_machinery WHERE machine_id = ?",
        (str(machine_id),))
    if row is None:
        raise LookupError(
            "maquina no encontrada: "
            + str(machine_id))
    return str(row["machine_id"])


def log_usage_db(db, *, machine_id, hours,
                 fuel_liters=0.0, operator="",
                 logged_at=""):
    ensure_db(db)
    _machine(db, machine_id)
    if float(hours) < 0 or float(fuel_liters) < 0:
        raise ValueError(
            "hours/fuel no negativos")
    uid = "MUSG-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_mach_usage (usage_id,"
        " machine_id, hours, fuel_liters, operator,"
        " logged_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, str(machine_id), float(hours),
         float(fuel_liters), str(operator),
         str(logged_at)))
    return {"usage_id": uid,
            "machine_id": str(machine_id),
            "hours": float(hours),
            "fuel_liters": float(fuel_liters)}


def log_maintenance_db(db, *, machine_id, kind,
                       detail="", cost=0.0,
                       done_at=""):
    ensure_db(db)
    _machine(db, machine_id)
    k = str(kind).upper()
    if k not in _MAINT:
        raise ValueError("kind debe ser "
                         + "/".join(_MAINT))
    if float(cost) < 0:
        raise ValueError("cost no negativo")
    mid = "MMNT-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_mach_maint (maint_id,"
        " machine_id, kind, detail, cost, done_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (mid, str(machine_id), k, str(detail),
         _sf(cost), str(done_at)))
    return {"maint_id": mid, "kind": k,
            "cost": _sf(cost)}


def open_order_db(db, *, machine_id, task,
                  opened_at=""):
    ensure_db(db)
    _machine(db, machine_id)
    oid = "MORD-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_mach_orders (order_id,"
        " machine_id, task, status, opened_at,"
        " closed_at) VALUES (?, ?, ?, 'open', ?,"
        " NULL)",
        (oid, str(machine_id), str(task),
         str(opened_at)))
    return {"order_id": oid, "status": "open"}


def close_order_db(db, order_id, *, ok=True,
                   closed_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_mach_orders WHERE"
        " order_id = ?", (str(order_id),))
    if row is None:
        raise KeyError(order_id)
    if str(row["status"]) != "open":
        raise ValueError(
            "orden ya procesada: "
            + str(row["status"]))
    new = "done" if ok else "cancelled"
    db.execute(
        "UPDATE agro_mach_orders SET status = ?,"
        " closed_at = ? WHERE order_id = ?",
        (new, str(closed_at), str(order_id)))
    return {"order_id": str(order_id),
            "status": new}


def summary_of_db(db, machine_id):
    ensure_db(db)
    _machine(db, machine_id)
    h = db.query_one(
        "SELECT COALESCE(SUM(hours), 0) AS h,"
        " COALESCE(SUM(fuel_liters), 0) AS f FROM"
        " agro_mach_usage WHERE machine_id = ?",
        (str(machine_id),))
    m = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(cost),"
        " 0) AS c FROM agro_mach_maint WHERE"
        " machine_id = ?", (str(machine_id),))
    o = db.query_one(
        "SELECT COUNT(*) AS n FROM agro_mach_orders"
        " WHERE machine_id = ? AND status = 'open'",
        (str(machine_id),))
    return {"machine_id": str(machine_id),
            "hours_total": float(h["h"]),
            "fuel_total": float(h["f"]),
            "maintenance_count": int(m["n"]),
            "maintenance_cost": float(m["c"]),
            "open_orders": int(o["n"])}
