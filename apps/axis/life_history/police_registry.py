
"""AXIS Police Registry (AX-6): agentes, denuncias,
buscados con ZID, capturas. Patron _DDL +
ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_pol_agents ("
    " agent_id TEXT PRIMARY KEY, name TEXT NOT"
    " NULL, unit TEXT NOT NULL DEFAULT '', active"
    " INTEGER NOT NULL DEFAULT 1, created_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_pol_denuncias ("
    " den_id TEXT PRIMARY KEY, complainant TEXT"
    " NOT NULL, against_person TEXT NOT NULL"
    " DEFAULT '', facts TEXT NOT NULL, status TEXT"
    " NOT NULL DEFAULT 'ingresada', police_actor"
    " TEXT NOT NULL DEFAULT '', created_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_pol_wanted ("
    " wanted_id TEXT PRIMARY KEY, person_id TEXT"
    " NOT NULL DEFAULT '', zid TEXT NOT NULL"
    " DEFAULT '', reason TEXT NOT NULL, ref_case"
    "_id TEXT NOT NULL DEFAULT '', status TEXT"
    " NOT NULL DEFAULT 'buscado', requested_by"
    " TEXT NOT NULL DEFAULT '', created_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_pol_captures ("
    " cap_id TEXT PRIMARY KEY, wanted_id TEXT NOT"
    " NULL, by_agent TEXT NOT NULL, captured_at"
    " TEXT NOT NULL DEFAULT '', released_at TEXT"
    " NOT NULL DEFAULT '')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_agent_db(db, *, name, unit="",
                      created_at=""):
    ensure_db(db)
    if not str(name).strip():
        raise ValueError("name requerido")
    aid = ("AXAG-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pol_agents (agent_id,"
        " name, unit, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (aid, str(name), str(unit),
         str(created_at)))
    return {"agent_id": aid, "name": str(name)}


def agents_of_db(db, only_active=True):
    ensure_db(db)
    if only_active:
        rows = db.query_all(
            "SELECT agent_id, name, unit FROM"
            " ax_pol_agents WHERE active = 1"
            " ORDER BY rowid")
    else:
        rows = db.query_all(
            "SELECT agent_id, name, unit FROM"
            " ax_pol_agents ORDER BY rowid")
    return [{"agent_id": str(r["agent_id"]),
             "name": str(r["name"]),
             "unit": str(r["unit"])}
            for r in rows]


def file_denuncia_db(db, *, complainant, facts,
                     against_person="",
                     police_actor="",
                     created_at=""):
    ensure_db(db)
    if not str(complainant).strip() or \
            not str(facts).strip():
        raise ValueError(
            "complainant y facts requeridos")
    did = ("AXDEN-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pol_denuncias (den_id,"
        " complainant, against_person, facts,"
        " status, police_actor, created_at)"
        " VALUES (?, ?, ?, ?, 'ingresada', ?,"
        " ?)",
        (did, str(complainant),
         str(against_person), str(facts),
         str(police_actor), str(created_at)))
    return {"den_id": did,
            "status": "ingresada"}


def advance_denuncia_db(db, den_id, *,
                        police_actor=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_pol_denuncias"
        " WHERE den_id = ?", (str(den_id),))
    if row is None:
        raise KeyError(den_id)
    cur = str(row["status"])
    flow = {"ingresada": "investigacion",
            "investigacion": "cerrada"}
    if cur not in flow:
        raise ValueError(
            "estado final: " + cur)
    db.execute(
        "UPDATE ax_pol_denuncias SET status = ?,"
        " police_actor = ? WHERE den_id = ?",
        (flow[cur], str(police_actor),
         str(den_id)))
    return {"den_id": str(den_id),
            "status": flow[cur]}


def denuncias_of_db(db, status=""):
    ensure_db(db)
    if str(status).strip():
        rows = db.query_all(
            "SELECT den_id, complainant, facts,"
            " status FROM ax_pol_denuncias WHERE"
            " status = ? ORDER BY rowid",
            (str(status),))
    else:
        rows = db.query_all(
            "SELECT den_id, complainant, facts,"
            " status FROM ax_pol_denuncias ORDER"
            " BY rowid")
    return [{"den_id": str(r["den_id"]),
             "complainant": str(
                 r["complainant"]),
             "facts": str(r["facts"]),
             "status": str(r["status"])}
            for r in rows]


def register_wanted_db(db, *, reason,
                       person_id="", zid="",
                       ref_case_id="",
                       requested_by="",
                       created_at=""):
    ensure_db(db)
    if not str(person_id).strip() and \
            not str(zid).strip():
        raise ValueError(
            "person_id o zid requerido")
    if not str(reason).strip():
        raise ValueError(
            "reason requerida")
    wid = ("AXW-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pol_wanted (wanted_id,"
        " person_id, zid, reason, ref_case_id,"
        " status, requested_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'buscado', ?,"
        " ?)",
        (wid, str(person_id), str(zid),
         str(reason), str(ref_case_id),
         str(requested_by), str(created_at)))
    return {"wanted_id": wid,
            "status": "buscado"}


def wanted_active_db(db):
    ensure_db(db)
    rows = db.query_all(
        "SELECT wanted_id, person_id, zid,"
        " reason, ref_case_id FROM"
        " ax_pol_wanted WHERE status = 'buscado'"
        " ORDER BY rowid")
    return [{"wanted_id": str(r["wanted_id"]),
             "person_id": str(r["person_id"]),
             "zid": str(r["zid"]),
             "reason": str(r["reason"]),
             "ref_case_id": str(
                 r["ref_case_id"])}
            for r in rows]


def capture_db(db, wanted_id, *, by_agent,
               captured_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_pol_wanted WHERE"
        " wanted_id = ?", (str(wanted_id),))
    if row is None:
        raise KeyError(wanted_id)
    if str(row["status"]) != "buscado":
        raise ValueError(
            "solo se captura a un buscado")
    if not str(by_agent).strip():
        raise ValueError(
            "by_agent requerido")
    cid = ("AXCAP-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pol_captures (cap_id,"
        " wanted_id, by_agent, captured_at,"
        " released_at) VALUES (?, ?, ?, ?, '')",
        (cid, str(wanted_id), str(by_agent),
         str(captured_at)))
    db.execute(
        "UPDATE ax_pol_wanted SET status ="
        " 'capturado' WHERE wanted_id = ?",
        (str(wanted_id),))
    return {"cap_id": cid,
            "status": "capturado"}


def release_capture_db(db, cap_id, *,
                       released_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT released_at FROM ax_pol_captures"
        " WHERE cap_id = ?", (str(cap_id),))
    if row is None:
        raise KeyError(cap_id)
    if str(row["released_at"]).strip():
        raise ValueError(
            "captura ya liberada")
    db.execute(
        "UPDATE ax_pol_captures SET released_at"
        " = ? WHERE cap_id = ?",
        (str(released_at), str(cap_id)))
    return {"cap_id": str(cap_id),
            "released": True}
