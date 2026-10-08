
"""Water Ops Engine (A-10): consumo de riego,
programacion semanal y balance hidrico sobre fuentes
existentes (agro_area_water, DDL confirmado).
Sobre-consumo del disponible -> ValueError honesto
(regla 66). Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_area_water ("
    " water_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, source_type TEXT NOT NULL,"
    " capacity_liters REAL NOT NULL, created_at"
    " REAL NOT NULL)",
    "CREATE TABLE IF NOT EXISTS agro_water_use ("
    " use_id TEXT PRIMARY KEY, water_id TEXT NOT"
    " NULL, volume_liters REAL NOT NULL, purpose"
    " TEXT NOT NULL DEFAULT '', used_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_water_sched ("
    " sched_id TEXT PRIMARY KEY, water_id TEXT NOT"
    " NULL, weekday TEXT NOT NULL, volume_planned"
    " REAL NOT NULL, active INTEGER NOT NULL"
    " DEFAULT 1)",
)
_DAYS = ("LUN", "MAR", "MIE", "JUE", "VIE",
         "SAB", "DOM")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _source(db, water_id):
    row = db.query_one(
        "SELECT capacity_liters FROM agro_area_water"
        " WHERE water_id = ?", (str(water_id),))
    if row is None:
        raise LookupError(
            "fuente no encontrada: "
            + str(water_id))
    return float(row["capacity_liters"])


def used_of_db(db, water_id):
    row = db.query_one(
        "SELECT COALESCE(SUM(volume_liters), 0) AS"
        " u FROM agro_water_use WHERE water_id = ?",
        (str(water_id),))
    return float(row["u"])


def register_use_db(db, *, water_id, volume_liters,
                    purpose="", used_at=""):
    ensure_db(db)
    cap = _source(db, water_id)
    if float(volume_liters) <= 0:
        raise ValueError("volume positiva")
    remaining = cap - used_of_db(db, water_id)
    if float(volume_liters) > remaining:
        raise ValueError(
            "sobre-consumo: pedido "
            + str(volume_liters)
            + ", disponible " + str(remaining))
    uid = "WUSE-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_water_use (use_id,"
        " water_id, volume_liters, purpose, used_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (uid, str(water_id), float(volume_liters),
         str(purpose), str(used_at)))
    return {"use_id": uid,
            "remaining_after":
                remaining - float(volume_liters)}


def schedule_db(db, *, water_id, weekday,
                volume_planned):
    ensure_db(db)
    _source(db, water_id)
    d = str(weekday).upper()
    if d not in _DAYS:
        raise ValueError("weekday debe ser "
                         + "/".join(_DAYS))
    if float(volume_planned) <= 0:
        raise ValueError("volume_planned positiva")
    sid = "WSCH-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_water_sched (sched_id,"
        " water_id, weekday, volume_planned, active)"
        " VALUES (?, ?, ?, ?, 1)",
        (sid, str(water_id), d,
         float(volume_planned)))
    return {"sched_id": sid, "weekday": d,
            "volume_planned":
                float(volume_planned)}


def sched_of_db(db, water_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT sched_id, weekday, volume_planned,"
        " active FROM agro_water_sched WHERE"
        " water_id = ? ORDER BY rowid",
        (str(water_id),))
    return [{"sched_id": str(r["sched_id"]),
             "weekday": str(r["weekday"]),
             "volume_planned": float(
                 r["volume_planned"]),
             "active": bool(int(r["active"]))}
            for r in rows]


def balance_of_db(db, water_id):
    ensure_db(db)
    cap = _source(db, water_id)
    used = used_of_db(db, water_id)
    sched = sched_of_db(db, water_id)
    planned = sum(s["volume_planned"]
                  for s in sched
                  if s["active"])
    remaining = cap - used
    return {"water_id": str(water_id),
            "capacity": cap, "used": used,
            "remaining": remaining,
            "planned_week": planned,
            "covers_week": remaining >= planned}


def uses_of_db(db, water_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT use_id, volume_liters, purpose,"
        " used_at FROM agro_water_use WHERE"
        " water_id = ? ORDER BY rowid",
        (str(water_id),))
    return [{"use_id": str(r["use_id"]),
             "volume_liters": float(
                 r["volume_liters"]),
             "purpose": str(r["purpose"]),
             "used_at": str(r["used_at"])}
            for r in rows]
