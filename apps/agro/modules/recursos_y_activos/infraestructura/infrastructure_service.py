
class InfrastructureService:
    def register(self, producer_id, kind, location=None):
        return {
            "producer_id": producer_id,
            "kind": kind,
            "location": location
        }


# ---- additive RUN E (GPT-5): infraestructura persistente ----
# Usa InfrastructureService.register() real.
def register_infrastructure_db(
    db, *, producer_id, kind,
    location=None,
):
    import time as _t
    import uuid as _u
    base = InfrastructureService().register(
        producer_id, kind, location
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_infrastructure ("
        " infra_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " location TEXT,"
        " created_at TEXT)"
    )
    infra_id = (
        "INF-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_infrastructure ("
        " infra_id, producer_id, kind,"
        " location, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (infra_id, producer_id, kind,
         location, ts),
    )
    out = dict(base)
    out["infra_id"] = infra_id
    return out


def infrastructure_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT infra_id,"
                    " producer_id, kind,"
                    " location, created_at FROM"
                    " agro_infrastructure WHERE"
                    " producer_id = ? ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
