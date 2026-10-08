
from apps.agro.shared.money import D2 as _D2, safe_float as _sf


class SimpleSaleService:
    def create(self, producer_id, product, quantity, buyer, price):
        if quantity <= 0 or price < 0:
            raise ValueError("Invalid quantity or price")

        return {
            "producer_id": producer_id,
            "product": product,
            "quantity": quantity,
            "buyer": buyer,
            "price": price
        }


# ---- additive PLUS (GPT-3): venta persistente ciclo completo ----
# Usa SimpleSaleService.create() y
# SalesService.calculate_total() reales.
from apps.agro.modules.comercializacion.ventas.sales_service import (
    SalesService,
)

SALE_STATES = (
    "listed", "offered", "accepted",
    "paid", "delivered", "closed",
)


def _sale_db(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_sales_plus ("
        " sale_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " remaining REAL NOT NULL,"
        " unit TEXT NOT NULL DEFAULT"
        " 'quintal',"
        " buyer TEXT,"
        " offer_price REAL,"
        " total REAL,"
        " currency TEXT NOT NULL DEFAULT"
        " 'USD',"
        " status TEXT NOT NULL,"
        " paid_at TEXT, delivered_at TEXT,"
        " closed_at TEXT, created_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_sale_offers ("
        " offer_id TEXT PRIMARY KEY,"
        " sale_id TEXT NOT NULL,"
        " buyer TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL DEFAULT"
        " 'USD',"
        " status TEXT NOT NULL,"
        " created_at TEXT)"
    )


def publish_sale_db(
    db, *, producer_id, product,
    quantity, unit="quintal",
    currency="USD",
):
    import time as _t
    import uuid as _u
    base = SimpleSaleService().create(
        producer_id, product, quantity,
        "market", 0
    )
    _sale_db(db)
    sale_id = (
        "SALP-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_sales_plus ("
        " sale_id, producer_id, product,"
        " quantity, remaining, unit,"
        " currency, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?,"
        " 'listed', ?)",
        (sale_id, producer_id, product,
         float(quantity), float(quantity),
         unit, str(currency).upper(), ts),
    )
    return {
        "sale_id": sale_id,
        "producer_id": producer_id,
        "product": product,
        "quantity": float(quantity),
        "remaining": float(quantity),
        "unit": unit,
        "currency": str(currency).upper(),
        "status": "listed",
    }


def place_offer_db(
    db, *, sale_id, buyer,
    amount, currency="USD",
):
    import time as _t
    import uuid as _u
    _sale_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status, remaining,"
                    " currency FROM"
                    " agro_sales_plus WHERE"
                    " sale_id = ?",
                    (sale_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "venta no encontrada: "
            + str(sale_id)
        )
    try:
        status = str(row["status"])
        remaining = float(row["remaining"])
        sale_cur = str(row["currency"])
    except Exception:
        status = str(row[0])
        remaining = float(row[1])
        sale_cur = str(row[2])
    if status != "listed":
        raise ValueError(
            "venta no disponible para"
            " ofertas (estado: " + status
            + ")"
        )
    amt = _sf(amount or 0)
    if amt <= 0:
        raise ValueError(
            "oferta debe ser positiva"
        )
    if str(currency).upper() != sale_cur:
        raise ValueError(
            "moneda de oferta difiere de"
            " la venta (conversion: motor"
            " transversal de la Red)"
        )
    offer_id = (
        "OFR-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_sale_offers ("
        " offer_id, sale_id, buyer, amount,"
        " currency, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'open', ?)",
        (offer_id, sale_id, buyer, amt,
         str(currency).upper(), ts),
    )
    return {
        "offer_id": offer_id,
        "sale_id": sale_id,
        "buyer": buyer,
        "amount": amt,
        "currency": str(currency).upper(),
        "status": "open",
    }


def accept_offer_db(
    db, *, offer_id, actor="anon",
):
    import time as _t
    _sale_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT offer_id, sale_id,"
                    " buyer, amount, currency,"
                    " status FROM"
                    " agro_sale_offers WHERE"
                    " offer_id = ?",
                    (offer_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "oferta no encontrada: "
            + str(offer_id)
        )
    try:
        sid = str(row["sale_id"])
        buyer = str(row["buyer"])
        amount = float(row["amount"])
        currency = str(row["currency"])
        status = str(row["status"])
    except Exception:
        sid = str(row[1])
        buyer = str(row[2])
        amount = float(row[3])
        currency = str(row[4])
        status = str(row[5])
    if status != "open":
        raise ValueError(
            "oferta ya procesada"
        )
    sale = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                sale = fn(
                    "SELECT status, remaining"
                    " FROM agro_sales_plus"
                    " WHERE sale_id = ?",
                    (sid,),
                )
            except Exception:
                sale = None
            if sale:
                break
    try:
        sale_status = str(sale["status"])
        remaining = float(sale["remaining"])
    except Exception:
        sale_status = str(sale[0])
        remaining = float(sale[1])
    if sale_status != "listed":
        raise ValueError(
            "venta no disponible (estado: "
            + sale_status + ")"
        )
    if remaining <= 0:
        raise ValueError(
            "sin existencias disponibles"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_sale_offers SET"
        " status = 'accepted' WHERE"
        " offer_id = ?",
        (offer_id,),
    )
    db.execute(
        "UPDATE agro_sales_plus SET"
        " status = 'offered', buyer = ?,"
        " offer_price = ?, currency = ?"
        " WHERE sale_id = ?",
        (buyer, amount, currency, sid),
    )
    total = SalesService().calculate_total(
        remaining, amount
    )
    return {
        "offer_id": offer_id,
        "sale_id": sid,
        "buyer": buyer,
        "amount": amount,
        "currency": currency,
        "total": _sf(total),
        "remaining": remaining,
    }


def pay_sale_db(
    db, *, sale_id, actor="anon",
):
    import time as _t
    _sale_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status, remaining,"
                    " offer_price, currency,"
                    " buyer FROM agro_sales_plus"
                    " WHERE sale_id = ?",
                    (sale_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "venta no encontrada: "
            + str(sale_id)
        )
    try:
        status = str(row["status"])
        remaining = float(row["remaining"])
        price = float(row["offer_price"])
        currency = str(row["currency"])
        buyer = str(row["buyer"])
    except Exception:
        status = str(row[0])
        remaining = float(row[1])
        price = float(row[2])
        currency = str(row[3])
        buyer = str(row[4])
    if status != "offered":
        raise ValueError(
            "pago requiere oferta aceptada"
            " (estado: " + status + ")"
        )
    total = SalesService().calculate_total(
        remaining, price
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_sales_plus SET"
        " status = 'paid', paid_at = ?,"
        " total = ? WHERE sale_id = ?",
        (ts, _sf(total), sale_id),
    )
    return {
        "sale_id": sale_id,
        "status": "paid",
        "buyer": buyer,
        "total": _sf(total),
        "currency": currency,
        "paid_at": ts,
    }


def deliver_sale_db(
    db, *, sale_id, actor="anon",
):
    import time as _t
    _sale_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status, remaining,"
                    " product, producer_id FROM"
                    " agro_sales_plus WHERE"
                    " sale_id = ?",
                    (sale_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "venta no encontrada: "
            + str(sale_id)
        )
    try:
        status = str(row["status"])
        remaining = float(row["remaining"])
        product = str(row["product"])
        pid = str(row["producer_id"])
    except Exception:
        status = str(row[0])
        remaining = float(row[1])
        product = str(row[2])
        pid = str(row[3])
    if status != "paid":
        raise ValueError(
            "entrega requiere pago previo"
            " (estado: " + status + ")"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_sales_plus SET"
        " status = 'delivered',"
        " delivered_at = ? WHERE"
        " sale_id = ?",
        (ts, sale_id),
    )
    return {
        "sale_id": sale_id,
        "status": "delivered",
        "product": product,
        "quantity_delivered": remaining,
        "producer_id": pid,
    }


def close_sale_db(
    db, *, sale_id, actor="anon",
):
    import time as _t
    _sale_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status, remaining,"
                    " product, producer_id,"
                    " unit FROM agro_sales_plus"
                    " WHERE sale_id = ?",
                    (sale_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "venta no encontrada: "
            + str(sale_id)
        )
    try:
        status = str(row["status"])
        remaining = float(row["remaining"])
        product = str(row["product"])
        pid = str(row["producer_id"])
        unit = str(row["unit"])
    except Exception:
        status = str(row[0])
        remaining = float(row[1])
        product = str(row[2])
        pid = str(row[3])
        unit = str(row[4])
    if status != "delivered":
        raise ValueError(
            "cierre requiere entrega previa"
            " (estado: " + status + ")"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_sales_plus SET"
        " status = 'closed', remaining = 0,"
        " closed_at = ? WHERE sale_id = ?",
        (ts, sale_id),
    )
    _deduct_inventory_db(
        db, producer_id=pid,
        product=product,
        quantity=remaining,
        unit=unit,
    )
    return {
        "sale_id": sale_id,
        "status": "closed",
        "inventory_deducted": {
            "product": product,
            "quantity": remaining,
            "unit": unit,
        },
    }


def _deduct_inventory_db(
    db, *, producer_id, product,
    quantity, unit,
):
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_inventory_plus ("
        " inv_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " unit TEXT NOT NULL,"
        " updated_at TEXT)"
    )
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT inv_id, quantity FROM"
                    " agro_inventory_plus WHERE"
                    " producer_id = ? AND"
                    " product = ?",
                    (producer_id, product),
                )
            except Exception:
                row = None
            if row:
                break
    import time as _t
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    if row:
        try:
            inv_id = row["inv_id"]
            current = float(row["quantity"])
        except Exception:
            inv_id = row[0]
            current = float(row[1])
        new_q = max(0.0, current - quantity)
        db.execute(
            "UPDATE agro_inventory_plus SET"
            " quantity = ?, updated_at = ?"
            " WHERE inv_id = ?",
            (new_q, ts, inv_id),
        )
    else:
        db.execute(
            "INSERT INTO"
            " agro_inventory_plus ("
            " producer_id, product,"
            " quantity, unit, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (producer_id, product,
             0.0, unit, ts),
        )


def inventory_add_db(
    db, *, producer_id, product,
    quantity, unit="quintal",
):
    import time as _t
    if float(quantity or 0) <= 0:
        raise ValueError(
            "cantidad debe ser positiva"
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_inventory_plus ("
        " inv_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " unit TEXT NOT NULL,"
        " updated_at TEXT)"
    )
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT inv_id FROM"
                    " agro_inventory_plus WHERE"
                    " producer_id = ? AND"
                    " product = ?",
                    (producer_id, product),
                )
            except Exception:
                row = None
            if row:
                break
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    if row:
        try:
            inv_id = row["inv_id"]
        except Exception:
            inv_id = row[0]
        db.execute(
            "UPDATE agro_inventory_plus SET"
            " quantity = quantity + ?,"
            " updated_at = ? WHERE"
            " inv_id = ?",
            (float(quantity), ts, inv_id),
        )
    else:
        db.execute(
            "INSERT INTO"
            " agro_inventory_plus ("
            " producer_id, product,"
            " quantity, unit, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (producer_id, product,
             float(quantity), unit, ts),
        )
    return {
        "producer_id": producer_id,
        "product": product,
        "quantity": float(quantity),
        "unit": unit,
    }


def inventory_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT producer_id, product,"
                    " quantity, unit, updated_at"
                    " FROM agro_inventory_plus"
                    " WHERE producer_id = ?"
                    " ORDER BY product",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def sales_of_db(db, producer_id=None):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                if producer_id:
                    got = fn(
                        "SELECT sale_id,"
                        " producer_id, product,"
                        " quantity, remaining,"
                        " unit, buyer,"
                        " offer_price, currency,"
                        " total, status,"
                        " created_at FROM"
                        " agro_sales_plus WHERE"
                        " producer_id = ?"
                        " ORDER BY created_at",
                        (producer_id,),
                    )
                else:
                    got = fn(
                        "SELECT sale_id,"
                        " producer_id, product,"
                        " quantity, remaining,"
                        " unit, buyer,"
                        " offer_price, currency,"
                        " total, status,"
                        " created_at FROM"
                        " agro_sales_plus"
                        " ORDER BY created_at"
                    )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def offers_of_db(db, sale_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT offer_id, sale_id,"
                    " buyer, amount, currency,"
                    " status, created_at FROM"
                    " agro_sale_offers WHERE"
                    " sale_id = ? ORDER BY"
                    " amount DESC",
                    (sale_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
