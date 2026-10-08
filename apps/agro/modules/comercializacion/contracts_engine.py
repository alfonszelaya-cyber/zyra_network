
"""Contracts Engine (A-11): comercializacion
avanzada — contratos (draft->signed->delivered->
liquidated; cancel solo antes de signed, regla 66),
ordenes de compra del comprador, y LIQUIDACION
(neto = bruto - deducciones, Decimal 2d via
money.py). Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_contracts ("
    " contract_id TEXT PRIMARY KEY, producer_id"
    " TEXT NOT NULL, buyer TEXT NOT NULL, product"
    " TEXT NOT NULL, quantity REAL NOT NULL, unit"
    " TEXT NOT NULL DEFAULT '', price REAL NOT"
    " NULL DEFAULT 0, currency TEXT NOT NULL"
    " DEFAULT 'USD', status TEXT NOT NULL DEFAULT"
    " 'draft', sale_id TEXT NOT NULL DEFAULT '',"
    " created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_contract_ocs ("
    " po_id TEXT PRIMARY KEY, contract_id TEXT NOT"
    " NULL, po_number TEXT NOT NULL, quantity REAL"
    " NOT NULL, amount REAL NOT NULL, status TEXT"
    " NOT NULL DEFAULT 'open', created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS"
    " agro_contract_liquidations (liq_id TEXT"
    " PRIMARY KEY, contract_id TEXT NOT NULL, gross"
    " REAL NOT NULL, deductions REAL NOT NULL"
    " DEFAULT 0, net REAL NOT NULL, currency TEXT"
    " NOT NULL DEFAULT 'USD', created_at TEXT)",
)
_FLOW = ("draft", "signed", "delivered",
         "liquidated")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _contract(db, contract_id):
    row = db.query_one(
        "SELECT * FROM agro_contracts WHERE"
        " contract_id = ?", (str(contract_id),))
    if row is None:
        raise LookupError(
            "contrato no encontrado: "
            + str(contract_id))
    return row


def create_contract_db(db, *, producer_id, buyer,
                       product, quantity, unit="",
                       price=0.0, currency="USD",
                       created_at=""):
    ensure_db(db)
    if float(quantity) <= 0:
        raise ValueError("quantity positiva")
    if float(price) < 0:
        raise ValueError("price no negativo")
    cid = "CTR-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_contracts (contract_id,"
        " producer_id, buyer, product, quantity,"
        " unit, price, currency, status, sale_id,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?,"
        " ?, 'draft', '', ?)",
        (cid, str(producer_id), str(buyer),
         str(product), float(quantity), str(unit),
         _sf(price), str(currency).upper(),
         str(created_at)))
    return {"contract_id": cid, "status": "draft"}


def advance_contract_db(db, contract_id, *,
                        actor="anon",
                        sale_id=""):
    ensure_db(db)
    row = _contract(db, contract_id)
    cur = str(row["status"])
    if cur == "cancelled":
        raise ValueError(
            "contrato cancelado: no avanza")
    if cur not in _FLOW or cur == "liquidated":
        raise ValueError("estado final: " + cur)
    nxt = _FLOW[_FLOW.index(cur) + 1]
    if nxt == "delivered" and sale_id:
        db.execute(
            "UPDATE agro_contracts SET sale_id = ?"
            " WHERE contract_id = ?",
            (str(sale_id), str(contract_id)))
    db.execute(
        "UPDATE agro_contracts SET status = ?"
        " WHERE contract_id = ?",
        (nxt, str(contract_id)))
    return {"contract_id": str(contract_id),
            "from": cur, "to": nxt}


def cancel_contract_db(db, contract_id, *,
                       reason=""):
    ensure_db(db)
    row = _contract(db, contract_id)
    if not str(reason).strip():
        raise ValueError(
            "cancelacion requiere motivo")
    if str(row["status"]) in ("signed",
                             "delivered",
                             "liquidated"):
        raise ValueError(
            "no se cancela un contrato "
            + str(row["status"]))
    db.execute(
        "UPDATE agro_contracts SET status ="
        " 'cancelled' WHERE contract_id = ?",
        (str(contract_id),))
    return {"contract_id": str(contract_id),
            "status": "cancelled"}


def add_purchase_order_db(db, *, contract_id,
                          po_number, quantity,
                          amount, created_at=""):
    ensure_db(db)
    row = _contract(db, contract_id)
    if str(row["status"]) != "signed":
        raise ValueError(
            "OC requiere contrato signed")
    if float(quantity) <= 0 or float(amount) <= 0:
        raise ValueError(
            "quantity/amount positivas")
    pid = "PO-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_contract_ocs (po_id,"
        " contract_id, po_number, quantity, amount,"
        " status, created_at) VALUES (?, ?, ?, ?, ?,"
        " 'open', ?)",
        (pid, str(contract_id), str(po_number),
         float(quantity), _sf(amount),
         str(created_at)))
    return {"po_id": pid,
            "amount": _sf(amount)}


def liquidate_db(db, contract_id, *, deductions=0.0,
                 created_at=""):
    ensure_db(db)
    row = _contract(db, contract_id)
    if str(row["status"]) != "delivered":
        raise ValueError(
            "liquidacion requiere delivered; estado:"
            " " + str(row["status"]))
    gross = _sf(float(row["quantity"])
                * float(row["price"]))
    ded = _sf(deductions)
    if ded < 0:
        raise ValueError("deducciones no negativas")
    if ded > gross:
        raise ValueError(
            "deducciones exceden el bruto")
    net = _sf(gross - ded)
    lid = "LIQ-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_contract_liquidations"
        " (liq_id, contract_id, gross, deductions,"
        " net, currency, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lid, str(contract_id), gross, ded, net,
         str(row["currency"]), str(created_at)))
    db.execute(
        "UPDATE agro_contracts SET status ="
        " 'liquidated' WHERE contract_id = ?",
        (str(contract_id),))
    return {"liq_id": lid, "gross": gross,
            "deductions": ded, "net": net,
            "currency": str(row["currency"])}


def contracts_of_db(db, producer_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT contract_id, buyer, product,"
        " quantity, unit, price, currency, status,"
        " sale_id FROM agro_contracts WHERE"
        " producer_id = ? ORDER BY rowid",
        (str(producer_id),))
    return [{"contract_id": str(r["contract_id"]),
             "buyer": str(r["buyer"]),
             "product": str(r["product"]),
             "quantity": float(r["quantity"]),
             "price": float(r["price"]),
             "currency": str(r["currency"]),
             "status": str(r["status"]),
             "sale_id": str(r["sale_id"])}
            for r in rows]
