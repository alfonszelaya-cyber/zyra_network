
"""Agro Security RBAC (A-15): usuarios con ZID
(regla 63), grants jerarquia read<write<admin,
sesiones TTL, dispositivos, recuperacion un solo
uso con hash. Patron _DDL + ensure_db."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_sec_users ("
    " user_id TEXT PRIMARY KEY, zid TEXT NOT NULL"
    " DEFAULT '', name TEXT NOT NULL, role TEXT NOT"
    " NULL, active INTEGER NOT NULL DEFAULT 1,"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS agro_sec_grants ("
    " grant_id TEXT PRIMARY KEY, user_id TEXT NOT"
    " NULL, resource TEXT NOT NULL, action TEXT NOT"
    " NULL, UNIQUE(user_id, resource, action))",
    "CREATE TABLE IF NOT EXISTS agro_sec_sessions ("
    " session_id TEXT PRIMARY KEY, user_id TEXT NOT"
    " NULL, expires_at REAL NOT NULL, closed_at REAL,"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS agro_sec_devices ("
    " device_id TEXT PRIMARY KEY, user_id TEXT NOT"
    " NULL, label TEXT NOT NULL DEFAULT '', active"
    " INTEGER NOT NULL DEFAULT 1, created_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS agro_sec_recovery ("
    " rec_id TEXT PRIMARY KEY, user_id TEXT NOT"
    " NULL, code_hash TEXT NOT NULL, used INTEGER NOT"
    " NULL DEFAULT 0, created_at TEXT NOT NULL"
    " DEFAULT '')",
)
_ROLES = ("productor", "ganadero", "gobierno",
          "banco", "auditor", "operador")
_ACTIONS = ("read", "write", "admin")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


def register_user_db(db, *, name, role, zid="",
                     created_at=""):
    ensure_db(db)
    if not str(name).strip():
        raise ValueError("name requerido")
    r = str(role).lower()
    if r not in _ROLES:
        raise ValueError("role debe ser "
                         + "/".join(_ROLES))
    if r in ("productor", "ganadero",
             "gobierno") and \
            not str(zid).strip():
        raise ValueError(
            "ese role exige ZID (regla 63)")
    uid = ("ASU-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_sec_users (user_id, zid,"
        " name, role, active, created_at)"
        " VALUES (?, ?, ?, ?, 1, ?)",
        (uid, str(zid), str(name), r,
         str(created_at)))
    return {"user_id": uid, "role": r}


def _user(db, user_id):
    row = db.query_one(
        "SELECT user_id, active FROM agro_sec_users"
        " WHERE user_id = ?", (str(user_id),))
    if row is None:
        raise LookupError(
            "usuario no encontrado: "
            + str(user_id))
    if int(row["active"]) != 1:
        raise ValueError("usuario inactivo")
    return row


def grant_db(db, *, user_id, resource, action):
    ensure_db(db)
    _user(db, user_id)
    a = str(action).lower()
    if a not in _ACTIONS:
        raise ValueError("action debe ser "
                         + "/".join(_ACTIONS))
    if not str(resource).strip():
        raise ValueError("resource requerido")
    dup = db.query_one(
        "SELECT grant_id FROM agro_sec_grants WHERE"
        " user_id = ? AND resource = ? AND action ="
        " ?", (str(user_id), str(resource), a))
    if dup is not None:
        raise ValueError("grant ya existe")
    gid = ("ASG-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_sec_grants (grant_id,"
        " user_id, resource, action)"
        " VALUES (?, ?, ?, ?)",
        (gid, str(user_id), str(resource), a))
    return {"grant_id": gid}


def check_db(db, *, user_id, resource, action):
    ensure_db(db)
    a = str(action).lower()
    if a not in _ACTIONS:
        raise ValueError("action invalida")
    row = db.query_one(
        "SELECT active FROM agro_sec_users WHERE"
        " user_id = ?", (str(user_id),))
    if row is None or int(row["active"]) != 1:
        return {"allowed": False,
                "reason": "usuario inexistente"
                          " o inactivo"}
    if a == "read":
        acts = ("read", "write", "admin")
    elif a == "write":
        acts = ("write", "admin")
    else:
        acts = ("admin",)
    ph = ",".join("?" * len(acts))
    g = db.query_one(
        "SELECT grant_id FROM agro_sec_grants WHERE"
        " user_id = ? AND resource = ? AND action"
        " IN (" + ph + ")",
        (str(user_id), str(resource)) + acts)
    return {"allowed": g is not None}


def open_session_db(db, *, user_id, ttl_seconds,
                    created_at=""):
    ensure_db(db)
    _user(db, user_id)
    if float(ttl_seconds) <= 0:
        raise ValueError("ttl positiva")
    sid = ("ASS-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_sec_sessions (session_id,"
        " user_id, expires_at, closed_at, created_at)"
        " VALUES (?, ?, ?, NULL, ?)",
        (sid, str(user_id), float(ttl_seconds),
         str(created_at)))
    return {"session_id": sid}


def session_ok_db(db, session_id, now):
    ensure_db(db)
    row = db.query_one(
        "SELECT expires_at, closed_at FROM"
        " agro_sec_sessions WHERE session_id = ?",
        (str(session_id),))
    if row is None:
        return {"ok": False,
                "reason": "no existe"}
    if row["closed_at"] is not None:
        return {"ok": False, "reason": "cerrada"}
    if float(row["expires_at"]) <= float(now):
        return {"ok": False, "reason": "expirada"}
    return {"ok": True}


def close_session_db(db, session_id, *, now):
    ensure_db(db)
    row = db.query_one(
        "SELECT closed_at FROM agro_sec_sessions"
        " WHERE session_id = ?",
        (str(session_id),))
    if row is None:
        raise KeyError(session_id)
    if row["closed_at"] is not None:
        raise ValueError("ya cerrada")
    db.execute(
        "UPDATE agro_sec_sessions SET closed_at = ?"
        " WHERE session_id = ?",
        (float(now), str(session_id)))
    return {"session_id": str(session_id)}


def register_device_db(db, *, user_id, label="",
                       created_at=""):
    ensure_db(db)
    _user(db, user_id)
    did = ("ASD-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_sec_devices (device_id,"
        " user_id, label, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (did, str(user_id), str(label),
         str(created_at)))
    return {"device_id": did}


def deactivate_device_db(db, device_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT active FROM agro_sec_devices WHERE"
        " device_id = ?", (str(device_id),))
    if row is None:
        raise KeyError(device_id)
    db.execute(
        "UPDATE agro_sec_devices SET active = 0"
        " WHERE device_id = ?",
        (str(device_id),))
    return {"device_id": str(device_id)}


def issue_recovery_db(db, *, user_id, code,
                      created_at=""):
    ensure_db(db)
    _user(db, user_id)
    if len(str(code)) < 8:
        raise ValueError("codigo minimo 8")
    rid = ("ASR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_sec_recovery (rec_id,"
        " user_id, code_hash, used, created_at)"
        " VALUES (?, ?, ?, 0, ?)",
        (rid, str(user_id), _sha(str(code)),
         str(created_at)))
    return {"rec_id": rid,
            "note": "no se guarda en claro"
                    " (regla 63)"}


def consume_recovery_db(db, *, user_id, code):
    ensure_db(db)
    row = db.query_one(
        "SELECT rec_id FROM agro_sec_recovery WHERE"
        " user_id = ? AND code_hash = ? AND used ="
        " 0", (str(user_id), _sha(str(code))))
    if row is None:
        return {"ok": False,
                "reason": "codigo invalido o"
                          " usado"}
    db.execute(
        "UPDATE agro_sec_recovery SET used = 1"
        " WHERE rec_id = ?",
        (str(row["rec_id"]),))
    return {"ok": True, "user_id": str(user_id)}
