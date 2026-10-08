
"""Agro Zyra Bridge (A-16): eventos bidireccionales
con idempotencia (idem_key UNIQUE), reintentos con
tope -> dead-letter TERMINAL hasta retry explicito
(fail sobre dead LANZA), inbox idempotente,
reconciliacion. Patron _DDL + ensure_db."""
from __future__ import annotations
import json as _j
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_outbox ("
    " event_id TEXT PRIMARY KEY, event_type TEXT NOT"
    " NULL, aggregate_id TEXT NOT NULL DEFAULT '',"
    " payload TEXT NOT NULL DEFAULT '{}', idem_key"
    " TEXT NOT NULL UNIQUE, status TEXT NOT NULL"
    " DEFAULT 'pendiente', attempts INTEGER NOT NULL"
    " DEFAULT 0, created_at TEXT NOT NULL DEFAULT"
    " '', sent_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS agro_inbox ("
    " msg_id TEXT PRIMARY KEY, source_app TEXT NOT"
    " NULL, event_type TEXT NOT NULL, payload TEXT"
    " NOT NULL DEFAULT '{}', idem_key TEXT NOT NULL"
    " UNIQUE, status TEXT NOT NULL DEFAULT"
    " 'recibido', attempts INTEGER NOT NULL DEFAULT"
    " 0, created_at TEXT NOT NULL DEFAULT '',"
    " processed_at TEXT NOT NULL DEFAULT '')",
)
_MAX_ATTEMPTS = 3


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def publish_outbox_db(db, *, event_type,
                      aggregate_id="", payload=None,
                      idem_key, created_at=""):
    ensure_db(db)
    if not str(event_type).strip():
        raise ValueError(
            "event_type requerido")
    if not str(idem_key).strip():
        raise ValueError(
            "idem_key requerida")
    row = db.query_one(
        "SELECT event_id FROM agro_outbox WHERE"
        " idem_key = ?", (str(idem_key),))
    if row is not None:
        return {"event_id": str(row["event_id"]),
                "duplicated": True}
    eid = ("AGO-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_outbox (event_id,"
        " event_type, aggregate_id, payload,"
        " idem_key, status, attempts, created_at,"
        " sent_at) VALUES (?, ?, ?, ?, ?,"
        " 'pendiente', 0, ?, '')",
        (eid, str(event_type), str(aggregate_id),
         _j.dumps(payload or {}, default=str),
         str(idem_key), str(created_at)))
    return {"event_id": eid, "duplicated": False,
            "status": "pendiente"}


def mark_sent_db(db, event_id, *, sent_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_outbox WHERE"
        " event_id = ?", (str(event_id),))
    if row is None:
        raise KeyError(event_id)
    if str(row["status"]) == "enviado":
        raise ValueError("ya enviado")
    db.execute(
        "UPDATE agro_outbox SET status = 'enviado',"
        " sent_at = ? WHERE event_id = ?",
        (str(sent_at), str(event_id)))
    return {"event_id": str(event_id),
            "status": "enviado"}


def fail_outbox_db(db, event_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status, attempts FROM agro_outbox"
        " WHERE event_id = ?", (str(event_id),))
    if row is None:
        raise KeyError(event_id)
    if str(row["status"]) == "enviado":
        raise ValueError(
            "no se falla un evento enviado")
    if str(row["status"]) == "dead":
        raise ValueError(
            "evento en dead-letter: use"
            " retry_dead_db (dead es TERMINAL)")
    n = int(row["attempts"]) + 1
    new = "dead" if n >= _MAX_ATTEMPTS \
        else "pendiente"
    db.execute(
        "UPDATE agro_outbox SET attempts = ?,"
        " status = ? WHERE event_id = ?",
        (n, new, str(event_id)))
    return {"event_id": str(event_id),
            "attempts": n, "status": new}


def retry_dead_db(db, event_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_outbox WHERE"
        " event_id = ?", (str(event_id),))
    if row is None:
        raise KeyError(event_id)
    if str(row["status"]) != "dead":
        raise ValueError(
            "no esta en dead-letter")
    db.execute(
        "UPDATE agro_outbox SET status ="
        " 'pendiente', attempts = 0 WHERE event_id"
        " = ?", (str(event_id),))
    return {"event_id": str(event_id),
            "status": "pendiente"}


def ingest_inbox_db(db, *, source_app, event_type,
                    payload=None, idem_key,
                    created_at=""):
    ensure_db(db)
    if not str(source_app).strip() or \
            not str(event_type).strip():
        raise ValueError(
            "source_app y event_type requeridos")
    if not str(idem_key).strip():
        raise ValueError("idem_key requerida")
    row = db.query_one(
        "SELECT msg_id FROM agro_inbox WHERE idem_key"
        " = ?", (str(idem_key),))
    if row is not None:
        return {"msg_id": str(row["msg_id"]),
                "duplicated": True}
    mid = ("AGI-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_inbox (msg_id, source_app,"
        " event_type, payload, idem_key, status,"
        " attempts, created_at, processed_at)"
        " VALUES (?, ?, ?, ?, ?, 'recibido', 0, ?,"
        " '')",
        (mid, str(source_app), str(event_type),
         _j.dumps(payload or {}, default=str),
         str(idem_key), str(created_at)))
    return {"msg_id": mid, "duplicated": False}


def process_inbox_db(db, msg_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM agro_inbox WHERE msg_id"
        " = ?", (str(msg_id),))
    if row is None:
        raise KeyError(msg_id)
    if str(row["status"]) == "procesado":
        raise ValueError("ya procesado")
    db.execute(
        "UPDATE agro_inbox SET status ="
        " 'procesado', processed_at = ? WHERE"
        " msg_id = ?", (str(at), str(msg_id)))
    return {"msg_id": str(msg_id),
            "status": "procesado"}


def fail_inbox_db(db, msg_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status, attempts FROM agro_inbox"
        " WHERE msg_id = ?", (str(msg_id),))
    if row is None:
        raise KeyError(msg_id)
    if str(row["status"]) == "procesado":
        raise ValueError(
            "no se falla un mensaje procesado")
    n = int(row["attempts"]) + 1
    new = "dead" if n >= _MAX_ATTEMPTS \
        else "recibido"
    db.execute(
        "UPDATE agro_inbox SET attempts = ?, status ="
        " ? WHERE msg_id = ?",
        (n, new, str(msg_id)))
    return {"msg_id": str(msg_id),
            "attempts": n, "status": new}


def reconcile_db(db):
    ensure_db(db)
    out_st = db.query_all(
        "SELECT status, COUNT(*) AS n FROM"
        " agro_outbox GROUP BY status")
    in_st = db.query_all(
        "SELECT status, COUNT(*) AS n FROM"
        " agro_inbox GROUP BY status")
    pend = db.query_all(
        "SELECT event_id FROM agro_outbox WHERE"
        " status = 'pendiente' ORDER BY rowid"
        " LIMIT 20")
    dead_o = db.query_all(
        "SELECT event_id FROM agro_outbox WHERE"
        " status = 'dead' ORDER BY rowid")
    dead_i = db.query_all(
        "SELECT msg_id FROM agro_inbox WHERE status"
        " = 'dead' ORDER BY rowid")
    return {"outbox": {str(r["status"]):
                       int(r["n"])
                       for r in out_st},
            "inbox": {str(r["status"]):
                      int(r["n"])
                      for r in in_st},
            "pendientes": [str(r["event_id"])
                           for r in pend],
            "dead_outbox": [str(r["event_id"])
                            for r in dead_o],
            "dead_inbox": [str(r["msg_id"])
                           for r in dead_i]}
