
"""SUBASTAS Radar VIP (SUB-4/13) - seguimiento de
oportunidades por comprador VIP con alertas solo a
calificados, y evento radar.offer_alert para el
CARTERO (patron que REEMPLAZA el punto-a-punto
historico radar_motor->axis). v2: import de _sf
RESTAURADO (era la causa del NameError). Patron
_DDL + ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_radar_watch ("
    " watch_id TEXT PRIMARY KEY, buyer TEXT NOT"
    " NULL, category TEXT NOT NULL, min_value REAL"
    " NOT NULL DEFAULT 0, created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_radar_alerts ("
    " alert_id TEXT PRIMARY KEY, buyer TEXT NOT"
    " NULL, category TEXT NOT NULL, ref TEXT NOT"
    " NULL, value REAL NOT NULL DEFAULT 0, detail"
    " TEXT NOT NULL DEFAULT '', created_at TEXT"
    " NOT NULL DEFAULT '')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def watch_db(db, *, buyer, category,
             min_value=0.0, created_at=""):
    ensure_db(db)
    if not str(buyer).strip() or \
            not str(category).strip():
        raise ValueError(
            "buyer y category requeridos")
    if float(min_value) < 0:
        raise ValueError(
            "min_value no negativo")
    wid = ("SBW-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_radar_watch (watch_id,"
        " buyer, category, min_value, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (wid, str(buyer), str(category),
         _sf(min_value), str(created_at)))
    return {"watch_id": wid}


def unwatch_db(db, watch_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT watch_id FROM sb_radar_watch WHERE"
        " watch_id = ?", (str(watch_id),))
    if row is None:
        raise KeyError(watch_id)
    db.execute(
        "DELETE FROM sb_radar_watch WHERE"
        " watch_id = ?", (str(watch_id),))
    return {"watch_id": str(watch_id),
            "removed": True}


def publish_offer_db(db, *, category, ref,
                     value=0.0, detail="",
                     created_at=""):
    """Publica oferta y dispara alertas a los VIP
    que siguen la categoria con min_value <= value.
    Cada alerta es evento para el cartero."""
    ensure_db(db)
    if not str(category).strip() or \
            not str(ref).strip():
        raise ValueError(
            "category y ref requeridos")
    watchers = db.query_all(
        "SELECT watch_id, buyer, min_value FROM"
        " sb_radar_watch WHERE category = ?",
        (str(category),))
    fired = []
    for w in watchers:
        if float(value) >= \
                float(w["min_value"]):
            aid = ("SBR-"
                   + uuid.uuid4().hex[:10])
            db.execute(
                "INSERT INTO sb_radar_alerts"
                " (alert_id, buyer, category,"
                " ref, value, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (aid, str(w["buyer"]),
                 str(category), str(ref),
                 _sf(value), str(detail),
                 str(created_at)))
            fired.append(str(w["buyer"]))
    return {"category": str(category),
            "ref": str(ref),
            "alerts_fired": len(fired),
            "buyers": fired,
            "event": "radar.offer_alert"}


def alerts_of_db(db, buyer):
    ensure_db(db)
    rows = db.query_all(
        "SELECT alert_id, category, ref, value"
        " FROM sb_radar_alerts WHERE buyer = ?"
        " ORDER BY rowid", (str(buyer),))
    return [{"alert_id": str(r["alert_id"]),
             "category": str(r["category"]),
             "ref": str(r["ref"]),
             "value": float(r["value"])}
            for r in rows]
