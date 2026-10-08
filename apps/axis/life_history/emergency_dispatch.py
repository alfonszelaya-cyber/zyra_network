
"""AX-15 Emergency Dispatch: incidentes, recursos,
despacho exclusivo, resolucion libera recursos.
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_em_incidents ("
    " inc_id TEXT PRIMARY KEY, kind TEXT NOT NULL,"
    " location TEXT NOT NULL, severity TEXT NOT"
    " NULL DEFAULT 'media', status TEXT NOT NULL"
    " DEFAULT 'reportado', description TEXT NOT"
    " NULL DEFAULT '', reported_by TEXT NOT NULL"
    " DEFAULT '', created_at TEXT NOT NULL"
    " DEFAULT '', resolved_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_em_resources ("
    " res_id TEXT PRIMARY KEY, kind TEXT NOT NULL,"
    " name TEXT NOT NULL, base TEXT NOT NULL"
    " DEFAULT '', status TEXT NOT NULL DEFAULT"
    " 'disponible', created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_em_dispatch ("
    " dis_id TEXT PRIMARY KEY, inc_id TEXT NOT"
    " NULL, res_id TEXT NOT NULL, dispatched_at"
    " TEXT NOT NULL DEFAULT '', released_at TEXT"
    " NOT NULL DEFAULT '')",
)
_INC = ("MEDICA", "INCENDIO", "DELITO",
        "RESCATE", "DESASTRE")
_SEV = ("baja", "media", "alta", "critica")
_RESK = ("AMBULANCIA", "BOMBEROS", "POLICIA",
         "RESCATE")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def report_incident_db(db, *, kind, location,
                       severity="media",
                       description="",
                       reported_by="",
                       at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _INC:
        raise ValueError("kind debe ser "
                         + "/".join(_INC))
    s = str(severity).lower()
    if s not in _SEV:
        raise ValueError("severity invalida")
    if not str(location).strip():
        raise ValueError(
            "location requerida")
    iid = ("AXEM-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_em_incidents (inc_id,"
        " kind, location, severity, status,"
        " description, reported_by, created_at)"
        " VALUES (?, ?, ?, ?, 'reportado', ?, ?,"
        " ?)",
        (iid, k, str(location), s,
         str(description), str(reported_by),
         str(at)))
    return {"inc_id": iid,
            "status": "reportado"}


def register_resource_db(db, *, kind, name,
                         base="", at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _RESK:
        raise ValueError("kind debe ser "
                         + "/".join(_RESK))
    if not str(name).strip():
        raise ValueError("name requerido")
    rid = ("AXER-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_em_resources (res_id,"
        " kind, name, base, status, created_at)"
        " VALUES (?, ?, ?, ?, 'disponible', ?)",
        (rid, k, str(name), str(base),
         str(at)))
    return {"res_id": rid, "kind": k}


def available_resources_db(db, kind=""):
    ensure_db(db)
    if str(kind).strip():
        rows = db.query_all(
            "SELECT res_id, kind, name FROM"
            " ax_em_resources WHERE status"
            " = 'disponible' AND kind = ? ORDER"
            " BY rowid", (str(kind).upper(),))
    else:
        rows = db.query_all(
            "SELECT res_id, kind, name FROM"
            " ax_em_resources WHERE status"
            " = 'disponible' ORDER BY rowid")
    return [{"res_id": str(r["res_id"]),
             "kind": str(r["kind"])}
            for r in rows]


def dispatch_db(db, inc_id, *, res_id, at=""):
    ensure_db(db)
    inc = db.query_one(
        "SELECT status FROM ax_em_incidents WHERE"
        " inc_id = ?", (str(inc_id),))
    if inc is None:
        raise KeyError(inc_id)
    if str(inc["status"]) != "reportado":
        raise ValueError(
            "incidente no reportado")
    res = db.query_one(
        "SELECT status FROM ax_em_resources"
        " WHERE res_id = ?", (str(res_id),))
    if res is None:
        raise KeyError(res_id)
    if str(res["status"]) != "disponible":
        raise ValueError(
            "recurso no disponible")
    did = ("AXED-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_em_dispatch (dis_id,"
        " inc_id, res_id, dispatched_at,"
        " released_at) VALUES (?, ?, ?, ?, '')",
        (did, str(inc_id), str(res_id),
         str(at)))
    db.execute(
        "UPDATE ax_em_incidents SET status ="
        " 'despachado' WHERE inc_id = ?",
        (str(inc_id),))
    db.execute(
        "UPDATE ax_em_resources SET status ="
        " 'despachado' WHERE res_id = ?",
        (str(res_id),))
    return {"dis_id": did,
            "status": "despachado"}


def resolve_incident_db(db, inc_id, *, at=""):
    ensure_db(db)
    inc = db.query_one(
        "SELECT status FROM ax_em_incidents WHERE"
        " inc_id = ?", (str(inc_id),))
    if inc is None:
        raise KeyError(inc_id)
    if str(inc["status"]) == "resuelto":
        raise ValueError("ya resuelto")
    rows = db.query_all(
        "SELECT dis_id, res_id FROM"
        " ax_em_dispatch WHERE inc_id = ? AND"
        " released_at = ''",
        (str(inc_id),))
    for r in rows:
        db.execute(
            "UPDATE ax_em_resources SET status ="
            " 'disponible' WHERE res_id = ?",
            (str(r["res_id"]),))
        db.execute(
            "UPDATE ax_em_dispatch SET"
            " released_at = ? WHERE dis_id ="
            " ?", (str(at), str(r["dis_id"])))
    db.execute(
        "UPDATE ax_em_incidents SET status ="
        " 'resuelto', resolved_at = ? WHERE"
        " inc_id = ?", (str(at),
                        str(inc_id)))
    return {"inc_id": str(inc_id),
            "status": "resuelto",
            "resources_freed": len(rows)}


def dispatches_of_db(db, inc_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT dis_id, res_id FROM"
        " ax_em_dispatch WHERE inc_id = ? ORDER"
        " BY rowid", (str(inc_id),))
    return [{"dis_id": str(r["dis_id"]),
             "res_id": str(r["res_id"])}
            for r in rows]
