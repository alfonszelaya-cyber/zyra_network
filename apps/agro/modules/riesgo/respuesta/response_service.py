
class RiskResponseService:
    def create(self, risk_id, actions):
        return {
            "risk_id": risk_id,
            "actions": list(actions),
            "status": "planned"
        }


# ---- additive RUN E (GPT-6): planes de respuesta ----
# Usa RiskResponseService.create() real.
RESPONSE_STATUSES = (
    "planned", "in_progress", "completed",
)


def create_response_db(
    db, *, producer_id, risk_id,
    actions, actor="anon",
):
    import json as _json
    import time as _t
    import uuid as _u
    if not list(actions or []):
        raise ValueError(
            "acciones obligatorias"
        )
    base = RiskResponseService().create(
        risk_id, actions
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_responses ("
        " response_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " risk_id TEXT NOT NULL,"
        " actions TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT,"
        " updated_at TEXT)"
    )
    response_id = (
        "RSP-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_responses ("
        " response_id, producer_id,"
        " risk_id, actions, status,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 'planned',"
        " ?, ?)",
        (response_id, producer_id,
         risk_id,
         _json.dumps(list(actions)),
         ts, ts),
    )
    out = dict(base)
    out["response_id"] = response_id
    out["producer_id"] = producer_id
    return out


def update_response_db(
    db, *, response_id, status,
):
    import time as _t
    if str(status) not in RESPONSE_STATUSES:
        raise ValueError(
            "estado invalido (validos: "
            + ", ".join(RESPONSE_STATUSES)
            + ")"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_responses SET"
        " status = ?, updated_at = ?"
        " WHERE response_id = ?",
        (str(status), ts, response_id),
    )
    return {
        "response_id": response_id,
        "status": str(status),
        "updated_at": ts,
    }


def responses_of_db(db, producer_id):
    import json as _json
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT response_id,"
                    " producer_id, risk_id,"
                    " actions, status,"
                    " created_at, updated_at"
                    " FROM agro_responses WHERE"
                    " producer_id = ? ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                out = []
                for r in got:
                    d = dict(r)
                    try:
                        d["actions"] = _json.loads(
                            str(d.get("actions"))
                        )
                    except Exception:
                        pass
                    out.append(d)
                return out
    return []
