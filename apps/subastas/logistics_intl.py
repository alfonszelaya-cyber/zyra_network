
"""SUBASTAS Logistics Intl (SUB-8): carriers, envios
con tracking, ADUANAS profundas regla 59
(internacionales con declaracion y arancel 2d,
entrega bloqueada hasta despacho). Patron _DDL +
ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_carriers ("
    " carrier_id TEXT PRIMARY KEY, name TEXT NOT"
    " NULL, scope TEXT NOT NULL DEFAULT 'nacional',"
    " active INTEGER NOT NULL DEFAULT 1, created_at"
    " TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_shipments ("
    " ship_id TEXT PRIMARY KEY, auction_id TEXT NOT"
    " NULL DEFAULT '', carrier_id TEXT NOT NULL,"
    " origin TEXT NOT NULL, destination TEXT NOT"
    " NULL, scope TEXT NOT NULL DEFAULT 'nacional',"
    " status TEXT NOT NULL DEFAULT 'creado',"
    " tracking TEXT NOT NULL DEFAULT '', created_at"
    " TEXT NOT NULL DEFAULT '', delivered_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_customs ("
    " cust_id TEXT PRIMARY KEY, ship_id TEXT NOT"
    " NULL, direction TEXT NOT NULL, declaration"
    " TEXT NOT NULL, tariff REAL NOT NULL DEFAULT"
    " 0, status TEXT NOT NULL DEFAULT 'pendiente',"
    " cleared_at TEXT NOT NULL DEFAULT '', created"
    "_at TEXT NOT NULL DEFAULT '')",
)
_SCOPES = ("nacional", "internacional")
_DIRS = ("EXPORTACION", "IMPORTACION")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_carrier_db(db, *, name,
                        scope="nacional",
                        created_at=""):
    ensure_db(db)
    if not str(name).strip():
        raise ValueError("name requerido")
    s = str(scope).lower()
    if s not in _SCOPES:
        raise ValueError("scope debe ser "
                         + "/".join(_SCOPES))
    cid = ("SBCR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_carriers (carrier_id,"
        " name, scope, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (cid, str(name), s, str(created_at)))
    return {"carrier_id": cid}


def create_shipment_db(db, *, carrier_id, origin,
                       destination, auction_id="",
                       at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT scope, active FROM sb_carriers"
        " WHERE carrier_id = ?",
        (str(carrier_id),))
    if row is None:
        raise LookupError(
            "carrier no encontrado")
    if int(row["active"]) != 1:
        raise ValueError("carrier inactivo")
    if not str(origin).strip() or \
            not str(destination).strip():
        raise ValueError(
            "origin/destination requeridos")
    sid = ("SBSH-"
           + uuid.uuid4().hex[:10])
    tk = ("TRK-"
          + uuid.uuid4().hex[:8].upper())
    db.execute(
        "INSERT INTO sb_shipments (ship_id,"
        " auction_id, carrier_id, origin,"
        " destination, scope, status, tracking,"
        " created_at, delivered_at) VALUES (?, ?,"
        " ?, ?, ?, ?, 'creado', ?, ?, '')",
        (sid, str(auction_id), str(carrier_id),
         str(origin), str(destination),
         str(row["scope"]), tk, str(at)))
    return {"ship_id": sid, "tracking": tk,
            "scope": str(row["scope"])}


def declare_customs_db(db, *, ship_id, direction,
                       declaration, tariff=0.0,
                       at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT scope FROM sb_shipments WHERE"
        " ship_id = ?", (str(ship_id),))
    if row is None:
        raise LookupError(
            "envio no encontrado")
    if str(row["scope"]) != "internacional":
        raise ValueError(
            "aduana solo en envios"
            " internacionales (regla 59)")
    d = str(direction).upper()
    if d not in _DIRS:
        raise ValueError("direction debe ser "
                         + "/".join(_DIRS))
    if not str(declaration).strip():
        raise ValueError(
            "declaration requerida")
    if float(tariff) < 0:
        raise ValueError("tariff no negativo")
    cid = ("SXCU-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_customs (cust_id, ship_id,"
        " direction, declaration, tariff, status,"
        " cleared_at, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'pendiente', '',"
        " ?)",
        (cid, str(ship_id), d,
         str(declaration), _sf(tariff),
         str(at)))
    return {"cust_id": cid,
            "tariff": _sf(tariff)}


def clear_customs_db(db, cust_id, *, at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM sb_customs WHERE"
        " cust_id = ?", (str(cust_id),))
    if row is None:
        raise KeyError(cust_id)
    if str(row["status"]) != "pendiente":
        raise ValueError("ya despachada")
    db.execute(
        "UPDATE sb_customs SET status ="
        " 'despachada', cleared_at = ? WHERE"
        " cust_id = ?",
        (str(at), str(cust_id)))
    return {"cust_id": str(cust_id),
            "status": "despachada"}


def deliver_shipment_db(db, ship_id, *,
                        at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status, scope FROM sb_shipments"
        " WHERE ship_id = ?", (str(ship_id),))
    if row is None:
        raise KeyError(ship_id)
    if str(row["status"]) == "entregado":
        raise ValueError("ya entregado")
    if str(row["scope"]) == "internacional":
        c = db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sb_customs WHERE ship_id = ? AND"
            " status = 'pendiente'",
            (str(ship_id),))
        if int(c["n"]) > 0:
            raise ValueError(
                "entrega bloqueada: aduana"
                " pendiente (regla 66)")
    db.execute(
        "UPDATE sb_shipments SET status ="
        " 'entregado', delivered_at = ? WHERE"
        " ship_id = ?", (str(at),
                         str(ship_id)))
    return {"ship_id": str(ship_id),
            "status": "entregado"}


def shipments_of_db(db, auction_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT ship_id, tracking, status FROM"
        " sb_shipments WHERE auction_id = ?"
        " ORDER BY rowid", (str(auction_id),))
    return [{"ship_id": str(r["ship_id"]),
             "tracking": str(r["tracking"]),
             "status": str(r["status"])}
            for r in rows]
