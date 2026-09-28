
class InventoryService:
    def __init__(self):
        self.stock = {}

    def add(self, item, quantity):
        self.stock[item] = self.stock.get(item, 0) + quantity
        return self.stock[item]

    def remove(self, item, quantity):
        current = self.stock.get(item, 0)

        if quantity > current:
            raise ValueError("Insufficient inventory")

        self.stock[item] = current - quantity
        return self.stock[item]


# ---- additive RUN E (GPT-5): historial de cambios de activos ----
# Trazabilidad completa: cada cambio de un activo
# queda registrado (quien, cuando, que). Las reglas
# de autorizacion ya aplican via matriz + guardia.
def asset_log_db(
    db, *, producer_id, asset_kind,
    asset_id, action, detail="",
    actor="anon",
):
    import time as _t
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_asset_log ("
        " log_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " asset_kind TEXT NOT NULL,"
        " asset_id TEXT NOT NULL,"
        " action TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT '',"
        " actor TEXT NOT NULL,"
        " created_at TEXT)"
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_asset_log ("
        " producer_id, asset_kind,"
        " asset_id, action, detail,"
        " actor, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (producer_id, asset_kind,
         asset_id, str(action),
         str(detail or ""), str(actor), ts),
    )
    return {
        "producer_id": producer_id,
        "asset_kind": asset_kind,
        "asset_id": asset_id,
        "action": str(action),
        "at": ts,
    }


def asset_history_of_db(
    db, producer_id, asset_kind=None,
):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                if asset_kind:
                    got = fn(
                        "SELECT log_id,"
                        " producer_id,"
                        " asset_kind, asset_id,"
                        " action, detail, actor,"
                        " created_at FROM"
                        " agro_asset_log WHERE"
                        " producer_id = ? AND"
                        " asset_kind = ? ORDER"
                        " BY log_id",
                        (producer_id,
                         asset_kind),
                    )
                else:
                    got = fn(
                        "SELECT log_id,"
                        " producer_id,"
                        " asset_kind, asset_id,"
                        " action, detail, actor,"
                        " created_at FROM"
                        " agro_asset_log WHERE"
                        " producer_id = ? ORDER"
                        " BY log_id",
                        (producer_id,),
                    )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
