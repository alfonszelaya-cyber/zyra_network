
"""SUBASTAS Risk & Protection (SUB-9/10): disputas
3 estados, fraud flags con ZyraRiskScore
INFORMATIVO (regla 57 — la Red NO censura).
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_disputes ("
    " disp_id TEXT PRIMARY KEY, auction_id TEXT NOT"
    " NULL, opened_by TEXT NOT NULL, reason TEXT"
    " NOT NULL, status TEXT NOT NULL DEFAULT"
    " 'abierta', resolution TEXT NOT NULL DEFAULT"
    " '', resolved_by TEXT NOT NULL DEFAULT '',"
    " created_at TEXT NOT NULL DEFAULT '',"
    " resolved_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_fraud_flags ("
    " flag_id TEXT PRIMARY KEY, target TEXT NOT"
    " NULL, kind TEXT NOT NULL, score INTEGER NOT"
    " NULL, detail TEXT NOT NULL DEFAULT '',"
    " flagged_by TEXT NOT NULL DEFAULT '',"
    " created_at TEXT NOT NULL DEFAULT '')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def open_dispute_db(db, *, auction_id, opened_by,
                    reason, at=""):
    ensure_db(db)
    if not str(reason).strip():
        raise ValueError(
            "reason requerida")
    did = ("SBDP-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_disputes (disp_id,"
        " auction_id, opened_by, reason, status,"
        " created_at) VALUES (?, ?, ?, ?,"
        " 'abierta', ?)",
        (did, str(auction_id), str(opened_by),
         str(reason), str(at)))
    return {"disp_id": did,
            "status": "abierta"}


def advance_dispute_db(db, disp_id, *, actor="",
                       at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM sb_disputes WHERE"
        " disp_id = ?", (str(disp_id),))
    if row is None:
        raise KeyError(disp_id)
    cur = str(row["status"])
    flow = {"abierta": "en_revision",
            "en_revision": "resuelta"}
    if cur not in flow:
        raise ValueError(
            "disputa ya resuelta")
    db.execute(
        "UPDATE sb_disputes SET status = ? WHERE"
        " disp_id = ?",
        (flow[cur], str(disp_id)))
    return {"disp_id": str(disp_id),
            "status": flow[cur]}


def resolve_dispute_db(db, disp_id, *, resolution,
                       resolved_by, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM sb_disputes WHERE"
        " disp_id = ?", (str(disp_id),))
    if row is None:
        raise KeyError(disp_id)
    if str(row["status"]) == "resuelta":
        raise ValueError("ya resuelta")
    if not str(resolution).strip():
        raise ValueError(
            "resolution requerida")
    db.execute(
        "UPDATE sb_disputes SET status ="
        " 'resuelta', resolution = ?,"
        " resolved_by = ?, resolved_at = ? WHERE"
        " disp_id = ?",
        (str(resolution), str(resolved_by),
         str(at), str(disp_id)))
    return {"disp_id": str(disp_id),
            "status": "resuelta"}


def flag_fraud_db(db, *, target, kind, score,
                  detail="", flagged_by="",
                  at=""):
    ensure_db(db)
    s = int(score)
    if s < 0 or s > 100:
        raise ValueError("score 0..100")
    if not str(kind).strip():
        raise ValueError("kind requerido")
    fid = ("SBF-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_fraud_flags (flag_id,"
        " target, kind, score, detail, flagged_by,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?,"
        " ?)",
        (fid, str(target), str(kind), s,
         str(detail), str(flagged_by),
         str(at)))
    return {"flag_id": fid, "score": s,
            "note": ("ZyraRiskScore"
                     " informativo — la Red"
                     " NO censura (regla"
                     " 57)")}


def fraud_of_db(db, target):
    ensure_db(db)
    rows = db.query_all(
        "SELECT flag_id, kind, score FROM"
        " sb_fraud_flags WHERE target = ? ORDER"
        " BY rowid", (str(target),))
    return [{"flag_id": str(r["flag_id"]),
             "kind": str(r["kind"]),
             "score": int(r["score"])}
            for r in rows]


def open_disputes_db(db):
    ensure_db(db)
    rows = db.query_all(
        "SELECT disp_id, auction_id, reason, status"
        " FROM sb_disputes WHERE status !="
        " 'resuelta' ORDER BY rowid")
    return [{"disp_id": str(r["disp_id"]),
             "reason": str(r["reason"]),
             "status": str(r["status"])}
            for r in rows]
