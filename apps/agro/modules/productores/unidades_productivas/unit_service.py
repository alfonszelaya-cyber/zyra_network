
class ProductiveUnitService:
    def __init__(self):
        self.units = {}

    def register(self, producer_id, unit):
        self.units.setdefault(producer_id, []).append(unit)
        return unit

    def list(self, producer_id):
        return list(self.units.get(producer_id, []))


# ---- additive PLUS (GPT-1): unidades persistentes ----
def register_unit_db(
    db, *, producer_id, name,
    unit_type="agricola", land_id=None,
):
    import time as _t
    import uuid as _u
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT producer_id FROM"
                    " agro_producers_v2 WHERE"
                    " producer_id = ?",
                    (producer_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "productor no encontrado: "
            + str(producer_id)
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_units ("
        " unit_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " name TEXT NOT NULL,"
        " unit_type TEXT NOT NULL,"
        " land_id TEXT, created_at TEXT,"
        " closed_at TEXT, closed_by TEXT)"
    )
    unit_id = "UNI-" + _u.uuid4().hex[:10]
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_units (unit_id,"
        " producer_id, name, unit_type,"
        " land_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (unit_id, producer_id, name,
         unit_type, land_id, ts),
    )
    return {
        "unit_id": unit_id,
        "producer_id": producer_id,
        "name": name,
        "unit_type": unit_type,
        "land_id": land_id,
    }


def units_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT unit_id, producer_id,"
                    " name, unit_type, land_id,"
                    " created_at, closed_at,"
                    " closed_by FROM agro_units"
                    " WHERE producer_id = ?"
                    " ORDER BY created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def close_unit_db(
    db, *, unit_id, reason, closed_by,
):
    import time as _t
    if not str(reason or "").strip():
        raise ValueError(
            "motivo de cierre obligatorio"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_units SET closed_at = ?,"
        " closed_by = ? WHERE unit_id = ?",
        (ts, str(closed_by), unit_id),
    )
    return {
        "unit_id": unit_id,
        "closed_at": ts,
        "closed_by": str(closed_by),
        "reason": str(reason),
    }


def unit_capacity_report_db(db, producer_id):
    units = units_of_db(db, producer_id)
    active = [
        u for u in units
        if not u.get("closed_at")
    ]
    by_type = {}
    for u in active:
        t = str(u.get("unit_type") or "?")
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "producer_id": producer_id,
        "units_total": len(units),
        "units_active": len(active),
        "by_type": by_type,
    }
