
"""AX-11 Border Control: puestos/agentes, cruces con
ALERTA de buscado (referencia ax_pol_wanted — su
dueno crea la tabla), vehiculos marcados,
inspecciones. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_border_posts ("
    " post_id TEXT PRIMARY KEY, name TEXT NOT"
    " NULL, kind TEXT NOT NULL DEFAULT"
    " 'terrestre', active INTEGER NOT NULL"
    " DEFAULT 1, created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS"
    " ax_border_agents (agent_id TEXT PRIMARY KEY,"
    " name TEXT NOT NULL, post_id TEXT NOT NULL"
    " DEFAULT '', active INTEGER NOT NULL DEFAULT"
    " 1, created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_border_cross ("
    " cross_id TEXT PRIMARY KEY, post_id TEXT NOT"
    " NULL, person_id TEXT NOT NULL DEFAULT '',"
    " zid TEXT NOT NULL DEFAULT '', direction TEXT"
    " NOT NULL, alert TEXT NOT NULL DEFAULT '',"
    " agent_id TEXT NOT NULL DEFAULT '', at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_border_vehicles ("
    " veh_id TEXT PRIMARY KEY, plate TEXT NOT NULL"
    " UNIQUE, flagged TEXT NOT NULL DEFAULT '',"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS"
    " ax_border_inspections (insp_id TEXT PRIMARY"
    " KEY, cross_id TEXT NOT NULL DEFAULT '',"
    " veh_id TEXT NOT NULL DEFAULT '', result TEXT"
    " NOT NULL, notes TEXT NOT NULL DEFAULT '',"
    " agent_id TEXT NOT NULL DEFAULT '', at TEXT"
    " NOT NULL DEFAULT '')",
)
_DIRS = ("ENTRADA", "SALIDA")
_POSTK = ("terrestre", "aereo", "maritimo")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_post_db(db, *, name, kind="terrestre",
                     created_at=""):
    ensure_db(db)
    if not str(name).strip():
        raise ValueError("name requerido")
    k = str(kind).lower()
    if k not in _POSTK:
        raise ValueError("kind debe ser "
                         + "/".join(_POSTK))
    pid = ("AXBP-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_border_posts (post_id,"
        " name, kind, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (pid, str(name), k, str(created_at)))
    return {"post_id": pid, "name": str(name)}


def register_bagent_db(db, *, name, post_id="",
                       created_at=""):
    ensure_db(db)
    if not str(name).strip():
        raise ValueError("name requerido")
    aid = ("AXBA-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_border_agents (agent_id,"
        " name, post_id, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (aid, str(name), str(post_id),
         str(created_at)))
    return {"agent_id": aid, "name": str(name)}


def cross_db(db, *, post_id, direction,
             person_id="", zid="", agent_id="",
             at=""):
    ensure_db(db)
    k = str(direction).upper()
    if k not in _DIRS:
        raise ValueError("direction debe ser "
                         + "/".join(_DIRS))
    if not str(person_id).strip() and \
            not str(zid).strip():
        raise ValueError(
            "person_id o zid requerido")
    alert = ""
    if str(zid).strip():
        w = db.query_one(
            "SELECT wanted_id FROM ax_pol_wanted"
            " WHERE zid = ? AND status ="
            " 'buscado' LIMIT 1",
            (str(zid),))
        if w is not None:
            alert = ("BUSCADO:"
                     + str(w["wanted_id"]))
    cid = ("AXBC-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_border_cross (cross_id,"
        " post_id, person_id, zid, direction,"
        " alert, agent_id, at) VALUES (?, ?, ?,"
        " ?, ?, ?, ?, ?)",
        (cid, str(post_id), str(person_id),
         str(zid), k, alert, str(agent_id),
         str(at)))
    return {"cross_id": cid, "direction": k,
            "alert": alert}


def crosses_of_db(db, post_id="", only_alerts=
                  False):
    ensure_db(db)
    if only_alerts:
        rows = db.query_all(
            "SELECT cross_id, zid, direction,"
            " alert, at FROM ax_border_cross"
            " WHERE alert != '' ORDER BY rowid")
    else:
        rows = db.query_all(
            "SELECT cross_id, zid, direction,"
            " alert, at FROM ax_border_cross"
            " ORDER BY rowid")
    return [{"cross_id": str(r["cross_id"]),
             "zid": str(r["zid"]),
             "alert": str(r["alert"])}
            for r in rows]


def flag_vehicle_db(db, *, plate, reason,
                    created_at=""):
    ensure_db(db)
    if not str(plate).strip() or \
            not str(reason).strip():
        raise ValueError(
            "plate y reason requeridos")
    db.execute(
        "INSERT OR REPLACE INTO"
        " ax_border_vehicles (veh_id, plate,"
        " flagged, created_at) VALUES (?, ?, ?,"
        " ?)",
        ("AXBV-" + uuid.uuid4().hex[:10],
         str(plate).upper(), str(reason),
         str(created_at)))
    return {"plate": str(plate).upper()}


def vehicle_status_db(db, plate):
    ensure_db(db)
    row = db.query_one(
        "SELECT flagged FROM ax_border_vehicles"
        " WHERE plate = ?",
        (str(plate).upper(),))
    if row is None:
        return {"flagged_bool": False}
    return {"flagged": str(row["flagged"]),
            "flagged_bool": bool(
                str(row["flagged"]).strip())}


def inspect_db(db, *, cross_id="", veh_id="",
               result, notes="", agent_id="",
               at=""):
    ensure_db(db)
    if not str(result).strip():
        raise ValueError(
            "result requerido")
    if not str(cross_id).strip() and \
            not str(veh_id).strip():
        raise ValueError(
            "inspeccion exige cruce o"
            " vehiculo")
    iid = ("AXBI-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_border_inspections"
        " (insp_id, cross_id, veh_id, result,"
        " notes, agent_id, at) VALUES (?, ?, ?, ?,"
        " ?, ?, ?)",
        (iid, str(cross_id), str(veh_id),
         str(result), str(notes),
         str(agent_id), str(at)))
    return {"insp_id": iid}


def inspections_of_db(db, ref_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT insp_id, result FROM"
        " ax_border_inspections WHERE cross_id ="
        " ? OR veh_id = ? ORDER BY rowid",
        (str(ref_id), str(ref_id)))
    return [{"insp_id": str(r["insp_id"]),
             "result": str(r["result"])}
            for r in rows]
