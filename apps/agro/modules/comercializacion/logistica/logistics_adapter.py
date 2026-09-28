
class LogisticsAdapter:
    def create_request(self, origin, destination, cargo):
        return {
            "origin": origin,
            "destination": destination,
            "cargo": cargo,
            "engine": "zyra_network.logistics"
        }


# ---- additive PLUS (GPT-3): logistica persistente ----
def create_shipment_db(
    db, *, sale_id, origin,
    destination, cargo,
):
    import time as _t
    import uuid as _u
    base = LogisticsAdapter().create_request(
        origin, destination, cargo
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_shipments ("
        " shipment_id TEXT PRIMARY KEY,"
        " sale_id TEXT NOT NULL,"
        " origin TEXT NOT NULL,"
        " destination TEXT NOT NULL,"
        " cargo TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " engine TEXT NOT NULL,"
        " created_at TEXT)"
    )
    shipment_id = (
        "SHPA-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_shipments ("
        " shipment_id, sale_id, origin,"
        " destination, cargo, status,"
        " engine, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'planned',"
        " ?, ?)",
        (shipment_id, sale_id, origin,
         destination, str(cargo),
         base["engine"], ts),
    )
    out = dict(base)
    out["shipment_id"] = shipment_id
    out["sale_id"] = sale_id
    out["status"] = "planned"
    return out


def mark_shipment_db(
    db, *, shipment_id, status,
):
    import time as _t
    allowed = ("in_transit", "delivered")
    if str(status) not in allowed:
        raise ValueError(
            "estado invalido (validos: "
            + ", ".join(allowed) + ")"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_shipments SET"
        " status = ? WHERE"
        " shipment_id = ?",
        (str(status), shipment_id),
    )
    return {
        "shipment_id": shipment_id,
        "status": str(status),
        "at": ts,
    }


def shipments_of_db(db, sale_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT shipment_id, sale_id,"
                    " origin, destination, cargo,"
                    " status, engine, created_at"
                    " FROM agro_shipments WHERE"
                    " sale_id = ? ORDER BY"
                    " created_at",
                    (sale_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
