
"""SUBASTAS Escrow & Finance (SUB-7): retencion,
release con liquidacion neto 2d, reembolso con
motivo, historial por vendedor. Patron _DDL +
ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_escrow ("
    " esc_id TEXT PRIMARY KEY, auction_id TEXT NOT"
    " NULL, buyer TEXT NOT NULL, seller TEXT NOT"
    " NULL, amount REAL NOT NULL, commission REAL"
    " NOT NULL DEFAULT 0, currency TEXT NOT NULL"
    " DEFAULT 'USD', status TEXT NOT NULL DEFAULT"
    " 'retenido', created_at TEXT NOT NULL DEFAULT"
    " '', released_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_liquidations ("
    " liq_id TEXT PRIMARY KEY, seller TEXT NOT"
    " NULL, auction_id TEXT NOT NULL DEFAULT '',"
    " gross REAL NOT NULL, commission REAL NOT"
    " NULL DEFAULT 0, net REAL NOT NULL, currency"
    " TEXT NOT NULL DEFAULT 'USD', created_at TEXT"
    " NOT NULL DEFAULT '')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def hold_db(db, *, auction_id, buyer, seller,
            amount, commission=0.0, currency="USD",
            created_at=""):
    ensure_db(db)
    if float(amount) <= 0:
        raise ValueError("amount positiva")
    if float(commission) < 0:
        raise ValueError(
            "commission no negativa")
    if float(commission) >= float(amount):
        raise ValueError(
            "commission excede el amount")
    eid = ("SBE-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_escrow (esc_id,"
        " auction_id, buyer, seller, amount,"
        " commission, currency, status, created_at,"
        " released_at) VALUES (?, ?, ?, ?, ?, ?, ?,"
        " 'retenido', ?, '')",
        (eid, str(auction_id), str(buyer),
         str(seller), _sf(amount), _sf(commission),
         str(currency).upper(), str(created_at)))
    return {"esc_id": eid, "status": "retenido"}


def _escrow(db, esc_id):
    row = db.query_one(
        "SELECT * FROM sb_escrow WHERE esc_id = ?",
        (str(esc_id),))
    if row is None:
        raise LookupError(
            "escrow no encontrado: "
            + str(esc_id))
    return row


def release_db(db, esc_id, *, at=""):
    ensure_db(db)
    row = _escrow(db, esc_id)
    if str(row["status"]) != "retenido":
        raise ValueError(
            "escrow no retenido")
    gross = float(row["amount"])
    comm = float(row["commission"])
    net = _sf(gross - comm)
    lid = ("SBL-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_liquidations (liq_id,"
        " seller, auction_id, gross, commission,"
        " net, currency, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (lid, str(row["seller"]),
         str(row["auction_id"]), gross, comm,
         net, str(row["currency"]),
         str(at)))
    db.execute(
        "UPDATE sb_escrow SET status ="
        " 'liberado', released_at = ? WHERE"
        " esc_id = ?",
        (str(at), str(esc_id)))
    return {"liq_id": lid, "gross": gross,
            "commission": comm, "net": net}


def refund_db(db, esc_id, *, reason="", at=""):
    ensure_db(db)
    row = _escrow(db, esc_id)
    if str(row["status"]) != "retenido":
        raise ValueError("no retenido")
    if not str(reason).strip():
        raise ValueError(
            "motivo obligatorio (regla 66)")
    db.execute(
        "UPDATE sb_escrow SET status ="
        " 'reembolsado', released_at = ? WHERE"
        " esc_id = ?",
        (str(at), str(esc_id)))
    return {"esc_id": str(esc_id),
            "status": "reembolsado"}


def escrows_of_db(db, buyer=None, seller=None):
    ensure_db(db)
    if buyer:
        rows = db.query_all(
            "SELECT esc_id, auction_id, amount,"
            " status FROM sb_escrow WHERE buyer = ?"
            " ORDER BY rowid", (str(buyer),))
    elif seller:
        rows = db.query_all(
            "SELECT esc_id, auction_id, amount,"
            " status FROM sb_escrow WHERE seller ="
            " ? ORDER BY rowid", (str(seller),))
    else:
        rows = db.query_all(
            "SELECT esc_id, auction_id, amount,"
            " status FROM sb_escrow ORDER BY"
            " rowid")
    return [{"esc_id": str(r["esc_id"]),
             "amount": float(r["amount"]),
             "status": str(r["status"])}
            for r in rows]


def liquidations_of_db(db, seller):
    ensure_db(db)
    rows = db.query_all(
        "SELECT liq_id, auction_id, gross,"
        " commission, net, currency FROM"
        " sb_liquidations WHERE seller = ? ORDER"
        " BY rowid", (str(seller),))
    return [{"liq_id": str(r["liq_id"]),
             "gross": float(r["gross"]),
             "commission": float(
                 r["commission"]),
             "net": float(r["net"]),
             "currency": str(
                 r["currency"])}
            for r in rows]
