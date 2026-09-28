
class MarketService:
    def snapshot(self, product, prices):
        values = [float(p) for p in prices]

        if not values:
            raise ValueError("Prices are required")

        return {
            "product": product,
            "minimum": min(values),
            "maximum": max(values),
            "average": sum(values) / len(values)
        }


# ---- additive PLUS (GPT-3): precios de mercado ----
def add_price_db(
    db, *, product, price, actor="anon",
):
    import time as _t
    p = float(price or 0)
    if p <= 0:
        raise ValueError(
            "precio debe ser positivo"
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_market_prices ("
        " price_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " product TEXT NOT NULL,"
        " price REAL NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)"
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_market_prices ("
        " product, price, actor, created_at)"
        " VALUES (?, ?, ?, ?)",
        (str(product), p, str(actor), ts),
    )
    return {
        "product": str(product),
        "price": p,
    }


def market_snapshot_db(db, product):
    rows = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT price FROM"
                    " agro_market_prices WHERE"
                    " product = ? ORDER BY"
                    " created_at DESC LIMIT 30",
                    (str(product),),
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break
    prices = []
    for r in rows:
        try:
            prices.append(float(r["price"]))
        except Exception:
            try:
                prices.append(float(r[0]))
            except Exception:
                pass
    if not prices:
        raise LookupError(
            "sin precios registrados para "
            + str(product)
        )
    return MarketService().snapshot(
        product, prices
    )
