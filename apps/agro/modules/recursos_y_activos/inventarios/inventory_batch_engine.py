
"""Inventory Batch Engine (A-8): lotes con
vencimiento, consumo FIFO (por entry_seq) o FEFO
(por vencimiento), movimientos IN/OUT trazables,
stock y vencidos. Stock insuficiente -> ValueError
honesto (solo si NECESITA mas de lo disponible —
pedir EXACTAMENTE lo disponible es legitimo).
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS"
    " agro_inventory_batches (batch_id TEXT PRIMARY"
    " KEY, producer_id TEXT NOT NULL, product TEXT"
    " NOT NULL, quantity REAL NOT NULL, unit TEXT"
    " NOT NULL DEFAULT '', expiry_date TEXT NOT"
    " NULL DEFAULT '', entry_seq INTEGER NOT NULL,"
    " created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_batch_moves ("
    " move_id TEXT PRIMARY KEY, batch_id TEXT NOT"
    " NULL, quantity REAL NOT NULL, direction TEXT"
    " NOT NULL, reason TEXT NOT NULL DEFAULT '',"
    " created_at TEXT)",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def add_batch_db(db, *, producer_id, product,
                 quantity, unit="", expiry_date="",
                 created_at=""):
    ensure_db(db)
    if float(quantity) <= 0:
        raise ValueError("cantidad positiva")
    seq_row = db.query_one(
        "SELECT COALESCE(MAX(entry_seq), 0) AS mx"
        " FROM agro_inventory_batches WHERE"
        " producer_id = ?", (str(producer_id),))
    seq = int(seq_row["mx"]) + 1
    bid = "BTCH-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_inventory_batches"
        " (batch_id, producer_id, product,"
        " quantity, unit, expiry_date, entry_seq,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?,"
        " ?)",
        (bid, str(producer_id), str(product),
         float(quantity), str(unit),
         str(expiry_date), seq, str(created_at)))
    db.execute(
        "INSERT INTO agro_batch_moves (move_id,"
        " batch_id, quantity, direction, reason,"
        " created_at) VALUES (?, ?, ?, 'IN', 'alta"
        " de lote', ?)",
        ("BMOV-" + uuid.uuid4().hex[:10], bid,
         float(quantity), str(created_at)))
    return {"batch_id": bid, "entry_seq": seq,
            "quantity": float(quantity)}


def _order(policy):
    p = str(policy).upper()
    if p == "FIFO":
        return p, "entry_seq ASC"
    if p == "FEFO":
        return (p, "CASE WHEN expiry_date = ''"
                   " THEN '9999-12-31' ELSE"
                   " expiry_date END ASC,"
                   " entry_seq ASC")
    raise ValueError("policy debe ser FIFO o FEFO")


def consume_db(db, *, producer_id, product,
               quantity, policy="FIFO",
               reason="", created_at=""):
    ensure_db(db)
    p, order = _order(policy)
    need = float(quantity)
    if need <= 0:
        raise ValueError("cantidad positiva")
    rows = db.query_all(
        "SELECT batch_id, quantity, expiry_date"
        " FROM agro_inventory_batches WHERE"
        " producer_id = ? AND product = ? AND"
        " quantity > 0 ORDER BY " + order,
        (str(producer_id), str(product)))
    available = sum(float(r["quantity"])
                    for r in rows)
    if available < need:
        raise ValueError(
            "stock insuficiente: pedido "
            + str(need) + ", disponible "
            + str(available) + " (" + p + ")")
    taken = []
    rest = need
    for r in rows:
        if rest <= 0:
            break
        bid = str(r["batch_id"])
        take = min(float(r["quantity"]), rest)
        db.execute(
            "UPDATE agro_inventory_batches SET"
            " quantity = quantity - ? WHERE"
            " batch_id = ?", (take, bid))
        db.execute(
            "INSERT INTO agro_batch_moves"
            " (move_id, batch_id, quantity,"
            " direction, reason, created_at)"
            " VALUES (?, ?, ?, 'OUT', ?, ?)",
            ("BMOV-" + uuid.uuid4().hex[:10],
             bid, take,
             str(reason) + " [" + p + "]",
             str(created_at)))
        taken.append({"batch_id": bid,
                      "taken": take,
                      "expiry": str(
                          r["expiry_date"])})
        rest -= take
    return {"policy": p, "consumed": need,
            "from_batches": taken}


def batches_of_db(db, producer_id, product=""):
    ensure_db(db)
    if str(product).strip():
        rows = db.query_all(
            "SELECT batch_id, product, quantity,"
            " unit, expiry_date, entry_seq FROM"
            " agro_inventory_batches WHERE"
            " producer_id = ? AND product = ?"
            " ORDER BY entry_seq",
            (str(producer_id), str(product)))
    else:
        rows = db.query_all(
            "SELECT batch_id, product, quantity,"
            " unit, expiry_date, entry_seq FROM"
            " agro_inventory_batches WHERE"
            " producer_id = ? ORDER BY entry_seq",
            (str(producer_id),))
    return [{"batch_id": str(r["batch_id"]),
             "product": str(r["product"]),
             "quantity": float(r["quantity"]),
             "unit": str(r["unit"]),
             "expiry_date": str(
                 r["expiry_date"]),
             "entry_seq": int(r["entry_seq"])}
            for r in rows]


def stock_of_db(db, producer_id, product=""):
    ensure_db(db)
    if str(product).strip():
        rows = db.query_all(
            "SELECT product, unit, SUM(quantity)"
            " AS total FROM"
            " agro_inventory_batches WHERE"
            " producer_id = ? AND product = ?"
            " GROUP BY product, unit",
            (str(producer_id), str(product)))
    else:
        rows = db.query_all(
            "SELECT product, unit, SUM(quantity)"
            " AS total FROM"
            " agro_inventory_batches WHERE"
            " producer_id = ? GROUP BY product,"
            " unit", (str(producer_id),))
    return [{"product": str(r["product"]),
             "unit": str(r["unit"]),
             "total": float(r["total"] or 0.0)}
            for r in rows]


def moves_of_db(db, batch_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT move_id, quantity, direction,"
        " reason, created_at FROM agro_batch_moves"
        " WHERE batch_id = ? ORDER BY rowid",
        (str(batch_id),))
    return [{"move_id": str(r["move_id"]),
             "quantity": float(r["quantity"]),
             "direction": str(r["direction"]),
             "reason": str(r["reason"]),
             "created_at": str(r["created_at"])}
            for r in rows]


def expired_of_db(db, producer_id, as_of=""):
    ensure_db(db)
    rows = db.query_all(
        "SELECT batch_id, product, quantity, unit,"
        " expiry_date FROM"
        " agro_inventory_batches WHERE"
        " producer_id = ? AND expiry_date != ''"
        " AND expiry_date <= ? AND quantity > 0"
        " ORDER BY expiry_date, rowid",
        (str(producer_id), str(as_of)))
    return [{"batch_id": str(r["batch_id"]),
             "product": str(r["product"]),
             "quantity": float(r["quantity"]),
             "expiry_date": str(
                 r["expiry_date"])}
            for r in rows]
