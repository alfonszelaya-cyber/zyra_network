
class EquipmentService:
    def register(self, owner_id, kind):
        return {
            "owner_id": owner_id,
            "kind": kind
        }


# ---- additive RUN E (GPT-5): equipos persistentes ----
# Usa EquipmentService.register() real.
def register_equipment_db(
    db, *, producer_id, kind,
    identifier=None,
):
    import time as _t
    import uuid as _u
    base = EquipmentService().register(
        producer_id, kind
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_equipment ("
        " equipment_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " identifier TEXT,"
        " created_at TEXT)"
    )
    equipment_id = (
        "EQP-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_equipment ("
        " equipment_id, producer_id, kind,"
        " identifier, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (equipment_id, producer_id,
         kind, identifier, ts),
    )
    out = dict(base)
    out["equipment_id"] = equipment_id
    return out


def equipment_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT equipment_id,"
                    " producer_id, kind,"
                    " identifier, created_at"
                    " FROM agro_equipment WHERE"
                    " producer_id = ? ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
