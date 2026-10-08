
"""AX-18a Notify Center: canales, prioridades,
bandeja, lectura unica, CRITICA pendiente (base
ZYRA-AMBER). Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_notifications ("
    " notif_id TEXT PRIMARY KEY, channel TEXT NOT"
    " NULL, target_kind TEXT NOT NULL, target TEXT"
    " NOT NULL, subject TEXT NOT NULL, body TEXT"
    " NOT NULL DEFAULT '', priority TEXT NOT NULL"
    " DEFAULT 'MEDIA', status TEXT NOT NULL"
    " DEFAULT 'enviada', read_at TEXT NOT NULL"
    " DEFAULT '', created_at TEXT NOT NULL"
    " DEFAULT '')",
)
_CH = ("SMS", "EMAIL", "PUSH")
_TK = ("ROL", "INSTITUCION", "PERSONA",
       "EMERGENCIA")
_PR = ("INFO", "MEDIA", "ALTA", "CRITICA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def send_db(db, *, channel, target_kind, target,
            subject, body="", priority="MEDIA",
            at=""):
    ensure_db(db)
    c = str(channel).upper()
    if c not in _CH:
        raise ValueError("channel invalido")
    tk = str(target_kind).upper()
    if tk not in _TK:
        raise ValueError("target_kind"
                         " invalido")
    if not str(target).strip() or \
            not str(subject).strip():
        raise ValueError(
            "target y subject requeridos")
    p = str(priority).upper()
    if p not in _PR:
        raise ValueError("priority invalida")
    nid = ("AXN-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_notifications (notif_id,"
        " channel, target_kind, target, subject,"
        " body, priority, status, read_at,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?,"
        " ?, 'enviada', '', ?)",
        (nid, c, tk, str(target), str(subject),
         str(body), p, str(at)))
    return {"notif_id": nid, "priority": p}


def send_emergency_db(db, *, target, subject,
                      body="", at=""):
    ensure_db(db)
    return send_db(
        db, channel="PUSH",
        target_kind="EMERGENCIA",
        target=str(target),
        subject=str(subject),
        body=str(body), priority="CRITICA",
        at=str(at))


def inbox_of_db(db, target, unread_only=False):
    ensure_db(db)
    if unread_only:
        rows = db.query_all(
            "SELECT notif_id, channel, subject,"
            " priority FROM ax_notifications"
            " WHERE target = ? AND read_at = ''"
            " ORDER BY rowid", (str(target),))
    else:
        rows = db.query_all(
            "SELECT notif_id, channel, subject,"
            " priority, read_at FROM"
            " ax_notifications WHERE target = ?"
            " ORDER BY rowid", (str(target),))
    out = []
    for r in rows:
        d = {"notif_id": str(r["notif_id"]),
             "channel": str(r["channel"]),
             "subject": str(r["subject"]),
             "priority": str(r["priority"])}
        if "read_at" in r.keys():
            d["read"] = str(r["read_at"])
        out.append(d)
    return out


def mark_read_db(db, notif_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT read_at FROM ax_notifications"
        " WHERE notif_id = ?", (str(notif_id),))
    if row is None:
        raise KeyError(notif_id)
    if str(row["read_at"]).strip():
        raise ValueError("ya leida")
    db.execute(
        "UPDATE ax_notifications SET read_at ="
        " ? WHERE notif_id = ?",
        (str(at), str(notif_id)))
    return {"notif_id": str(notif_id),
            "read": True}


def critical_pending_db(db):
    ensure_db(db)
    rows = db.query_all(
        "SELECT notif_id, target, subject FROM"
        " ax_notifications WHERE priority ="
        " 'CRITICA' AND read_at = '' ORDER BY"
        " rowid")
    return [{"notif_id": str(r["notif_id"]),
             "target": str(r["target"]),
             "subject": str(r["subject"])}
            for r in rows]
