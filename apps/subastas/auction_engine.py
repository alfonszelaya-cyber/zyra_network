
"""SUBASTAS Auction Engine (SUB-3/5): lotes con
incremento minimo, pujas validadas, adjudicacion con
comision 2d, cancelacion SOLO sin pujas (regla 66)
con closed_at propio (v2: el reason ya no se filtra
a la columna closed_at). Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_auctions ("
    " auction_id TEXT PRIMARY KEY, title TEXT NOT"
    " NULL, category TEXT NOT NULL DEFAULT 'general',"
    " base_price REAL NOT NULL, min_increment REAL"
    " NOT NULL DEFAULT 1, currency TEXT NOT NULL"
    " DEFAULT 'USD', status TEXT NOT NULL DEFAULT"
    " 'activa', winner_id TEXT NOT NULL DEFAULT"
    " '', winner_bid REAL NOT NULL DEFAULT 0,"
    " created_at TEXT NOT NULL DEFAULT '', closed_at"
    " TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_bids ("
    " bid_id TEXT PRIMARY KEY, auction_id TEXT NOT"
    " NULL, bidder TEXT NOT NULL, amount REAL NOT"
    " NULL, created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_commissions ("
    " comm_id TEXT PRIMARY KEY, auction_id TEXT NOT"
    " NULL, winner_id TEXT NOT NULL, base REAL NOT"
    " NULL, rate_pct REAL NOT NULL, amount REAL NOT"
    " NULL, currency TEXT NOT NULL DEFAULT 'USD')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def create_auction_db(db, *, title, base_price,
                      category="general",
                      min_increment=1.0,
                      currency="USD",
                      created_at=""):
    ensure_db(db)
    if not str(title).strip():
        raise ValueError("title requerido")
    if float(base_price) <= 0:
        raise ValueError(
            "base_price positiva")
    if float(min_increment) <= 0:
        raise ValueError(
            "min_increment positiva")
    aid = ("SBA-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_auctions (auction_id,"
        " title, category, base_price, min_increment,"
        " currency, status, winner_id, winner_bid,"
        " created_at, closed_at) VALUES (?, ?, ?, ?,"
        " ?, ?, 'activa', '', 0, ?, '')",
        (aid, str(title), str(category),
         _sf(base_price), _sf(min_increment),
         str(currency).upper(), str(created_at)))
    return {"auction_id": aid,
            "status": "activa"}


def _auction(db, auction_id):
    row = db.query_one(
        "SELECT * FROM sb_auctions WHERE auction_id"
        " = ?", (str(auction_id),))
    if row is None:
        raise LookupError(
            "subasta no encontrada: "
            + str(auction_id))
    return row


def place_bid_db(db, *, auction_id, bidder, amount,
                 created_at=""):
    ensure_db(db)
    row = _auction(db, auction_id)
    if str(row["status"]) != "activa":
        raise ValueError(
            "subasta no activa: "
            + str(row["status"]))
    amt = _sf(amount)
    if amt <= 0:
        raise ValueError("puja positiva")
    if not str(bidder).strip():
        raise ValueError("bidder requerido")
    last = db.query_one(
        "SELECT amount FROM sb_bids WHERE"
        " auction_id = ? ORDER BY amount DESC"
        " LIMIT 1", (str(auction_id),))
    min_needed = (float(row["base_price"])
                  if last is None
                  else float(last["amount"])
                  + float(row["min_increment"]))
    if amt < min_needed:
        raise ValueError(
            "puja minima requerida: "
            + str(min_needed))
    bid = ("SBB-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_bids (bid_id, auction_id,"
        " bidder, amount, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (bid, str(auction_id), str(bidder), amt,
         str(created_at)))
    return {"bid_id": bid, "amount": amt,
            "min_next": _sf(min_needed
                            + float(row[
                                "min_increment"]))}


def bids_of_db(db, auction_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT bid_id, bidder, amount, created_at"
        " FROM sb_bids WHERE auction_id = ? ORDER"
        " BY amount DESC, rowid",
        (str(auction_id),))
    return [{"bid_id": str(r["bid_id"]),
             "bidder": str(r["bidder"]),
             "amount": float(r["amount"])}
            for r in rows]


def award_db(db, auction_id, *, rate_pct=5.0,
             closed_at=""):
    ensure_db(db)
    row = _auction(db, auction_id)
    if str(row["status"]) != "activa":
        raise ValueError(
            "solo se adjudica una activa")
    top = db.query_one(
        "SELECT bidder, amount FROM sb_bids WHERE"
        " auction_id = ? ORDER BY amount DESC"
        " LIMIT 1", (str(auction_id),))
    if top is None:
        raise ValueError(
            "sin pujas: no se adjudica"
            " (regla 66)")
    rate = _sf(rate_pct)
    if rate < 0 or rate > 100:
        raise ValueError("rate_pct 0..100")
    base = _sf(top["amount"])
    comm = _sf(base * rate / 100.0)
    wid = str(top["bidder"])
    db.execute(
        "UPDATE sb_auctions SET status ="
        " 'adjudicada', winner_id = ?, winner_bid"
        " = ?, closed_at = ? WHERE auction_id = ?",
        (wid, base, str(closed_at),
         str(auction_id)))
    cid = ("SBC-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_commissions (comm_id,"
        " auction_id, winner_id, base, rate_pct,"
        " amount, currency) VALUES (?, ?, ?, ?, ?,"
        " ?, ?)",
        (cid, str(auction_id), wid, base, rate,
         comm, str(row["currency"])))
    return {"status": "adjudicada",
            "winner_id": wid,
            "winner_bid": base,
            "commission": comm,
            "currency": str(row["currency"])}


def cancel_auction_db(db, auction_id, *,
                      reason="", closed_at=""):
    ensure_db(db)
    row = _auction(db, auction_id)
    if str(row["status"]) != "activa":
        raise ValueError(
            "solo se cancela una activa")
    if not str(reason).strip():
        raise ValueError(
            "motivo obligatorio")
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM sb_bids WHERE"
        " auction_id = ?", (str(auction_id),))
    if int(n["n"]) > 0:
        raise ValueError(
            "no se cancela con pujas"
            " (regla 66)")
    db.execute(
        "UPDATE sb_auctions SET status ="
        " 'cancelada', closed_at = ? WHERE"
        " auction_id = ?",
        (str(closed_at), str(auction_id)))
    return {"auction_id": str(auction_id),
            "status": "cancelada"}


def auction_of_db(db, auction_id):
    ensure_db(db)
    row = _auction(db, auction_id)
    return {"auction_id": str(
                row["auction_id"]),
            "title": str(row["title"]),
            "status": str(row["status"]),
            "base_price": float(
                row["base_price"]),
            "winner_id": str(
                row["winner_id"]),
            "winner_bid": float(
                row["winner_bid"])}


def active_auctions_db(db, category=""):
    ensure_db(db)
    if str(category).strip():
        rows = db.query_all(
            "SELECT auction_id, title, category,"
            " base_price FROM sb_auctions WHERE"
            " status = 'activa' AND category = ?"
            " ORDER BY rowid",
            (str(category),))
    else:
        rows = db.query_all(
            "SELECT auction_id, title, category,"
            " base_price FROM sb_auctions WHERE"
            " status = 'activa' ORDER BY rowid")
    return [{"auction_id": str(
                 r["auction_id"]),
             "title": str(r["title"]),
             "category": str(r["category"]),
             "base_price": float(
                 r["base_price"])}
            for r in rows]
