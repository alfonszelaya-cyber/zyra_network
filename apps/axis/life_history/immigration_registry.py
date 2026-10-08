
"""AX-10 Immigration: entradas/salidas, visas con
vencimiento, residencia, ciudadania sin duplicado,
deportacion. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_mig_moves ("
    " move_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, zid TEXT NOT NULL DEFAULT '', kind TEXT"
    " NOT NULL, checkpoint TEXT NOT NULL DEFAULT"
    " '', at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_mig_visas ("
    " visa_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, status TEXT NOT"
    " NULL DEFAULT 'solicitada', issued_at TEXT"
    " NOT NULL DEFAULT '', expires_at TEXT NOT"
    " NULL DEFAULT '', notes TEXT NOT NULL DEFAULT"
    " '')",
    "CREATE TABLE IF NOT EXISTS ax_mig_residency ("
    " res_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, status TEXT NOT"
    " NULL DEFAULT 'vigente', granted_at TEXT NOT"
    " NULL DEFAULT '', notes TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_mig_citizenship ("
    " cit_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, granted_by TEXT NOT NULL, granted_at"
    " TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_mig_deport ("
    " dep_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, reason TEXT NOT NULL, status TEXT NOT"
    " NULL DEFAULT 'ordenada', ordered_by TEXT NOT"
    " NULL, executed_at TEXT NOT NULL DEFAULT '',"
    " created_at TEXT NOT NULL DEFAULT '')",
)
_VISA = ("TURISTA", "TRABAJO", "ESTUDIANTE",
         "TRANSITO")
_RESK = ("TEMPORAL", "PERMANENTE")
_MOVE = ("ENTRADA", "SALIDA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _person_ok(db, person_id):
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido")
    return str(person_id)


def register_move_db(db, *, person_id, zid="",
                     kind, checkpoint="",
                     at=""):
    ensure_db(db)
    _person_ok(db, person_id)
    k = str(kind).upper()
    if k not in _MOVE:
        raise ValueError("kind debe ser "
                         + "/".join(_MOVE))
    mid = ("AXMV-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_mig_moves (move_id,"
        " person_id, zid, kind, checkpoint, at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (mid, str(person_id), str(zid), k,
         str(checkpoint), str(at)))
    return {"move_id": mid, "kind": k}


def moves_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT move_id, kind, checkpoint, at"
        " FROM ax_mig_moves WHERE person_id = ?"
        " ORDER BY rowid", (str(person_id),))
    return [{"move_id": str(r["move_id"]),
             "kind": str(r["kind"]),
             "checkpoint": str(r["checkpoint"])}
            for r in rows]


def apply_visa_db(db, *, person_id, kind,
                  notes="", at=""):
    ensure_db(db)
    _person_ok(db, person_id)
    k = str(kind).upper()
    if k not in _VISA:
        raise ValueError("kind debe ser "
                         + "/".join(_VISA))
    vid = ("AXV-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_mig_visas (visa_id,"
        " person_id, kind, status, issued_at,"
        " expires_at, notes) VALUES (?, ?, ?,"
        " 'solicitada', '', '', ?)",
        (vid, str(person_id), k, str(notes)))
    return {"visa_id": vid,
            "status": "solicitada"}


def decide_visa_db(db, visa_id, *, approve,
                   expires_at="", actor="",
                   at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_mig_visas WHERE"
        " visa_id = ?", (str(visa_id),))
    if row is None:
        raise KeyError(visa_id)
    if str(row["status"]) != "solicitada":
        raise ValueError(
            "visa ya decidida")
    new = "aprobada" if approve \
        else "rechazada"
    db.execute(
        "UPDATE ax_mig_visas SET status = ?,"
        " issued_at = ?, expires_at = ? WHERE"
        " visa_id = ?",
        (new, str(at), str(expires_at),
         str(visa_id)))
    return {"visa_id": str(visa_id),
            "status": new}


def expire_visa_db(db, visa_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_mig_visas WHERE"
        " visa_id = ?", (str(visa_id),))
    if row is None:
        raise KeyError(visa_id)
    if str(row["status"]) != "aprobada":
        raise ValueError(
            "solo se vence una aprobada")
    db.execute(
        "UPDATE ax_mig_visas SET status ="
        " 'vencida' WHERE visa_id = ?",
        (str(visa_id),))
    return {"visa_id": str(visa_id),
            "status": "vencida"}


def visas_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT visa_id, kind, status, expires_at"
        " FROM ax_mig_visas WHERE person_id = ?"
        " ORDER BY rowid", (str(person_id),))
    return [{"visa_id": str(r["visa_id"]),
             "kind": str(r["kind"]),
             "status": str(r["status"])}
            for r in rows]


def grant_residency_db(db, *, person_id, kind,
                       notes="", at=""):
    ensure_db(db)
    _person_ok(db, person_id)
    k = str(kind).upper()
    if k not in _RESK:
        raise ValueError("kind debe ser "
                         + "/".join(_RESK))
    rid = ("AXR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_mig_residency (res_id,"
        " person_id, kind, status, granted_at,"
        " notes) VALUES (?, ?, ?, 'vigente', ?,"
        " ?)",
        (rid, str(person_id), k, str(at),
         str(notes)))
    return {"res_id": rid, "kind": k,
            "status": "vigente"}


def cancel_residency_db(db, res_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_mig_residency"
        " WHERE res_id = ?", (str(res_id),))
    if row is None:
        raise KeyError(res_id)
    if str(row["status"]) != "vigente":
        raise ValueError("no vigente")
    db.execute(
        "UPDATE ax_mig_residency SET status ="
        " 'cancelada' WHERE res_id = ?",
        (str(res_id),))
    return {"res_id": str(res_id),
            "status": "cancelada"}


def residency_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT res_id, kind, status, granted_at"
        " FROM ax_mig_residency WHERE person_id ="
        " ? ORDER BY rowid", (str(person_id),))
    return [{"res_id": str(r["res_id"]),
             "kind": str(r["kind"])}
            for r in rows]


def naturalize_db(db, *, person_id, granted_by,
                  at=""):
    ensure_db(db)
    _person_ok(db, person_id)
    if not str(granted_by).strip():
        raise ValueError(
            "granted_by requerido")
    dup = db.query_one(
        "SELECT cit_id FROM ax_mig_citizenship"
        " WHERE person_id = ?",
        (str(person_id),))
    if dup is not None:
        raise ValueError(
            "ya naturalizado (regla 66)")
    cid = ("AXC-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_mig_citizenship (cit_id,"
        " person_id, granted_by, granted_at)"
        " VALUES (?, ?, ?, ?)",
        (cid, str(person_id), str(granted_by),
         str(at)))
    return {"cit_id": cid,
            "status": "naturalizado"}


def order_deportation_db(db, *, person_id,
                         reason, ordered_by,
                         at=""):
    ensure_db(db)
    _person_ok(db, person_id)
    if not str(reason).strip():
        raise ValueError(
            "reason requerida")
    did = ("AXD-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_mig_deport (dep_id,"
        " person_id, reason, status, ordered_by,"
        " executed_at, created_at)"
        " VALUES (?, ?, ?, 'ordenada', ?, '',"
        " ?)",
        (did, str(person_id), str(reason),
         str(ordered_by), str(at)))
    return {"dep_id": did,
            "status": "ordenada"}


def execute_deportation_db(db, dep_id, *,
                           at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_mig_deport WHERE"
        " dep_id = ?", (str(dep_id),))
    if row is None:
        raise KeyError(dep_id)
    if str(row["status"]) != "ordenada":
        raise ValueError("ya ejecutada")
    db.execute(
        "UPDATE ax_mig_deport SET status ="
        " 'ejecutada', executed_at = ? WHERE"
        " dep_id = ?",
        (str(at), str(dep_id)))
    return {"dep_id": str(dep_id),
            "status": "ejecutada"}


def deportations_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT dep_id, reason, status FROM"
        " ax_mig_deport WHERE person_id = ?"
        " ORDER BY rowid", (str(person_id),))
    return [{"dep_id": str(r["dep_id"]),
             "reason": str(r["reason"])}
            for r in rows]
