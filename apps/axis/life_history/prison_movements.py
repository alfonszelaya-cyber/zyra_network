
"""AX-12 Prison Movements: clasificacion, traslados,
visitas, liberacion que sincroniza ax_justice_pris.
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_justice_pris ("
    " pris_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL, person_id TEXT NOT NULL, zid TEXT NOT"
    " NULL DEFAULT '', sentence_days INTEGER NOT"
    " NULL DEFAULT 0, status TEXT NOT NULL DEFAULT"
    " 'preso', entry_by TEXT NOT NULL, entry_at"
    " TEXT NOT NULL DEFAULT '', exit_at TEXT NOT"
    " NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_pris_moves ("
    " move_id TEXT PRIMARY KEY, pris_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, from_center TEXT"
    " NOT NULL DEFAULT '', to_center TEXT NOT"
    " NULL DEFAULT '', detail TEXT NOT NULL"
    " DEFAULT '', at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_pris_visits ("
    " visit_id TEXT PRIMARY KEY, pris_id TEXT NOT"
    " NULL, visitor TEXT NOT NULL, allowed INTEGER"
    " NOT NULL DEFAULT 1, at TEXT NOT NULL"
    " DEFAULT '')",
)
_RISK = ("BAJO", "MEDIO", "ALTO", "MAXIMO")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _prison(db, pris_id):
    row = db.query_one(
        "SELECT pris_id, status, person_id FROM"
        " ax_justice_pris WHERE pris_id = ?",
        (str(pris_id),))
    if row is None:
        raise LookupError(
            "preso no encontrado: "
            + str(pris_id))
    return row


def classify_db(db, pris_id, *, risk, center,
                at=""):
    ensure_db(db)
    _prison(db, pris_id)
    r = str(risk).upper()
    if r not in _RISK:
        raise ValueError("risk debe ser "
                         + "/".join(_RISK))
    if not str(center).strip():
        raise ValueError("center requerido")
    mid = ("AXPM-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pris_moves (move_id,"
        " pris_id, kind, from_center, to_center,"
        " detail, at) VALUES (?, ?,"
        " 'CLASIFICACION', '', ?, ?, ?)",
        (mid, str(pris_id), str(center),
         "riesgo " + r, str(at)))
    return {"move_id": mid, "risk": r,
            "center": str(center)}


def transfer_db(db, pris_id, *, from_center,
                to_center, at=""):
    ensure_db(db)
    row = _prison(db, pris_id)
    if str(row["status"]) != "preso":
        raise ValueError(
            "solo se traslada a un preso")
    if not str(to_center).strip():
        raise ValueError(
            "to_center requerido")
    mid = ("AXPM-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pris_moves (move_id,"
        " pris_id, kind, from_center, to_center,"
        " detail, at) VALUES (?, ?, 'TRASLADO',"
        " ?, ?, '', ?)",
        (mid, str(pris_id), str(from_center),
         str(to_center), str(at)))
    return {"move_id": mid, "kind": "TRASLADO",
            "to_center": str(to_center)}


def visit_db(db, pris_id, *, visitor,
             allowed=True, at=""):
    ensure_db(db)
    row = _prison(db, pris_id)
    if str(row["status"]) != "preso":
        raise ValueError(
            "visitas solo a presos")
    if not str(visitor).strip():
        raise ValueError(
            "visitor requerido")
    vid = ("AXPV-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pris_visits (visit_id,"
        " pris_id, visitor, allowed, at)"
        " VALUES (?, ?, ?, ?, ?)",
        (vid, str(pris_id), str(visitor),
         1 if allowed else 0, str(at)))
    return {"visit_id": vid,
            "allowed": bool(allowed)}


def release_here_db(db, pris_id, *, at=""):
    ensure_db(db)
    row = _prison(db, pris_id)
    if str(row["status"]) != "preso":
        raise ValueError("ya liberado")
    mid = ("AXPM-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_pris_moves (move_id,"
        " pris_id, kind, from_center, to_center,"
        " detail, at) VALUES (?, ?,"
        " 'LIBERACION', '', '', '', ?)",
        (mid, str(pris_id), str(at)))
    db.execute(
        "UPDATE ax_justice_pris SET status ="
        " 'libre', exit_at = ? WHERE pris_id ="
        " ?", (str(at), str(pris_id)))
    return {"move_id": mid,
            "status": "libre"}


def movements_of_db(db, pris_id):
    ensure_db(db)
    _prison(db, pris_id)
    rows = db.query_all(
        "SELECT move_id, kind, from_center,"
        " to_center, detail, at FROM"
        " ax_pris_moves WHERE pris_id = ? ORDER"
        " BY rowid", (str(pris_id),))
    return [{"move_id": str(r["move_id"]),
             "kind": str(r["kind"]),
             "from_center": str(
                 r["from_center"]),
             "to_center": str(
                 r["to_center"]),
             "detail": str(r["detail"])}
            for r in rows]


def visits_of_db(db, pris_id):
    ensure_db(db)
    _prison(db, pris_id)
    rows = db.query_all(
        "SELECT visit_id, visitor, allowed, at"
        " FROM ax_pris_visits WHERE pris_id = ?"
        " ORDER BY rowid", (str(pris_id),))
    return [{"visit_id": str(r["visit_id"]),
             "visitor": str(r["visitor"]),
             "allowed": bool(
                 int(r["allowed"]))}
            for r in rows]
