
from apps.agro.shared.money import safe_float as _sf


class AssetValuationService:
    def value(self, asset_id, amount, currency):
        if amount < 0:
            raise ValueError("Amount cannot be negative")

        return {
            "asset_id": asset_id,
            "amount": amount,
            "currency": currency
        }


# ---- additive RUN E (GPT-5): valoracion persistente ----
# Usa AssetValuationService.value() real (valida
# amount >= 0).
def value_asset_db(
    db, *, producer_id, asset_kind,
    asset_id, amount, currency,
    actor="anon",
):
    import time as _t
    import uuid as _u
    base = AssetValuationService().value(
        asset_id, _sf(amount or 0), currency
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_valuations ("
        " valuation_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " asset_kind TEXT NOT NULL,"
        " asset_id TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)"
    )
    valuation_id = (
        "VAL-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_valuations ("
        " valuation_id, producer_id,"
        " asset_kind, asset_id, amount,"
        " currency, actor, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (valuation_id, producer_id,
         asset_kind, asset_id,
         _sf(amount),
         str(currency).upper(), actor, ts),
    )
    out = dict(base)
    out["valuation_id"] = valuation_id
    out["producer_id"] = producer_id
    out["asset_kind"] = asset_kind
    return out


def valuations_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT valuation_id,"
                    " producer_id, asset_kind,"
                    " asset_id, amount, currency,"
                    " actor, created_at FROM"
                    " agro_valuations WHERE"
                    " producer_id = ? ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def latest_value_of_db(
    db, producer_id, asset_id,
):
    for name in ("query_one", "query"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT amount, currency,"
                    " created_at FROM"
                    " agro_valuations WHERE"
                    " producer_id = ? AND"
                    " asset_id = ? ORDER BY"
                    " created_at DESC LIMIT 1",
                    (producer_id, asset_id),
                )
            except Exception:
                row = None
            if row:
                return dict(row)
    return None
