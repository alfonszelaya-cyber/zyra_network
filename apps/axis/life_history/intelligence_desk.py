
"""AX-13 Intelligence Desk: fuentes, informes
clasificados, entidades con ZID, vinculos
(LookupError en inexistentes), correlacion.
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_int_sources ("
    " source_id TEXT PRIMARY KEY, codename TEXT"
    " NOT NULL, reliability TEXT NOT NULL DEFAULT"
    " 'media', active INTEGER NOT NULL DEFAULT 1,"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_int_reports ("
    " report_id TEXT PRIMARY KEY, source_id TEXT"
    " NOT NULL, classification TEXT NOT NULL"
    " DEFAULT 'CONFIDENCIAL', body TEXT NOT NULL,"
    " filed_by TEXT NOT NULL DEFAULT '', at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_int_entities ("
    " ent_id TEXT PRIMARY KEY, kind TEXT NOT NULL,"
    " name TEXT NOT NULL, zid TEXT NOT NULL"
    " DEFAULT '', created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_int_links ("
    " link_id TEXT PRIMARY KEY, ent_a TEXT NOT"
    " NULL, ent_b TEXT NOT NULL, relation TEXT"
    " NOT NULL DEFAULT '', created_at TEXT NOT"
    " NULL DEFAULT '')",
)
_CLASS = ("CONFIDENCIAL", "SECRETO",
          "ULTRASECRETO")
_KINDS = ("PERSONA", "ORGANIZACION", "VEHICULO",
          "CUENTA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_source_db(db, *, codename,
                       reliability="media",
                       created_at=""):
    ensure_db(db)
    if not str(codename).strip():
        raise ValueError(
            "codename requerido")
    r = str(reliability).lower()
    if r not in ("alta", "media", "baja"):
        raise ValueError(
            "reliability alta/media/baja")
    sid = ("AXIS-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_int_sources (source_id,"
        " codename, reliability, active,"
        " created_at) VALUES (?, ?, ?, 1, ?)",
        (sid, str(codename), r,
         str(created_at)))
    return {"source_id": sid}


def file_report_db(db, *, source_id, body,
                   classification=
                   "CONFIDENCIAL",
                   filed_by="", at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT active FROM ax_int_sources WHERE"
        " source_id = ?", (str(source_id),))
    if row is None:
        raise LookupError(
            "fuente no encontrada")
    if int(row["active"]) != 1:
        raise ValueError("fuente inactiva")
    if not str(body).strip():
        raise ValueError("body requerido")
    c = str(classification).upper()
    if c not in _CLASS:
        raise ValueError(
            "classification invalida")
    rid = ("AXIR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_int_reports (report_id,"
        " source_id, classification, body,"
        " filed_by, at) VALUES (?, ?, ?, ?, ?,"
        " ?)",
        (rid, str(source_id), c, str(body),
         str(filed_by), str(at)))
    return {"report_id": rid,
            "classification": c}


def reports_of_db(db, classification=""):
    ensure_db(db)
    if str(classification).strip():
        rows = db.query_all(
            "SELECT report_id, classification,"
            " body FROM ax_int_reports WHERE"
            " classification = ? ORDER BY rowid",
            (str(classification).upper(),))
    else:
        rows = db.query_all(
            "SELECT report_id, classification,"
            " body FROM ax_int_reports ORDER BY"
            " rowid")
    return [{"report_id": str(r["report_id"]),
             "classification": str(
                 r["classification"])}
            for r in rows]


def register_entity_db(db, *, kind, name,
                       zid="", created_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(name).strip():
        raise ValueError("name requerido")
    eid = ("AXIE-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_int_entities (ent_id,"
        " kind, name, zid, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (eid, k, str(name), str(zid),
         str(created_at)))
    return {"ent_id": eid, "kind": k}


def link_entities_db(db, *, ent_a, ent_b,
                     relation="",
                     created_at=""):
    ensure_db(db)
    for eid in (ent_a, ent_b):
        row = db.query_one(
            "SELECT ent_id FROM ax_int_entities"
            " WHERE ent_id = ?", (str(eid),))
        if row is None:
            raise LookupError(
                "entidad no encontrada: "
                + str(eid))
    if str(ent_a) == str(ent_b):
        raise ValueError(
            "auto-vinculo invalido")
    lid = ("AXIL-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_int_links (link_id,"
        " ent_a, ent_b, relation, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (lid, str(ent_a), str(ent_b),
         str(relation), str(created_at)))
    return {"link_id": lid,
            "relation": str(relation)}


def correlations_of_db(db, ent_id):
    ensure_db(db)
    reports = db.query_all(
        "SELECT report_id FROM ax_int_reports"
        " ORDER BY rowid")
    links = db.query_all(
        "SELECT link_id, ent_a, ent_b, relation"
        " FROM ax_int_links WHERE ent_a = ? OR"
        " ent_b = ? ORDER BY rowid",
        (str(ent_id), str(ent_id)))
    ent = db.query_one(
        "SELECT name, kind, zid FROM"
        " ax_int_entities WHERE ent_id = ?",
        (str(ent_id),))
    return {"entity": (
                {"name": str(
                     ent["name"]),
                 "zid": str(ent["zid"])}
                if ent is not None
                else None),
            "reports_total": len(reports),
            "links": [{"link_id": str(
                l["link_id"]),
                "relation": str(
                    l["relation"])}
                for l in links]}
