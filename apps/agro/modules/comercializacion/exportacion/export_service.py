
class ExportService:
    def create_operation(self, product, destination, quantity):
        return {
            "product": product,
            "destination": destination,
            "quantity": quantity,
            "status": "planned"
        }


# ---- additive PLUS (GPT-3): exportacion persistente ----
def create_export_db(
    db, *, producer_id, product,
    destination, quantity,
):
    import time as _t
    import uuid as _u
    base = ExportService().create_operation(
        product, destination, quantity
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_exports ("
        " export_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " destination TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT)"
    )
    export_id = (
        "EXP-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_exports ("
        " export_id, producer_id, product,"
        " destination, quantity, status,"
        " created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (export_id, producer_id, product,
         destination, float(quantity),
         base["status"], ts),
    )
    out = dict(base)
    out["export_id"] = export_id
    out["producer_id"] = producer_id
    return out


def exports_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT export_id,"
                    " producer_id, product,"
                    " destination, quantity,"
                    " status, created_at FROM"
                    " agro_exports WHERE"
                    " producer_id = ?"
                    " ORDER BY created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
