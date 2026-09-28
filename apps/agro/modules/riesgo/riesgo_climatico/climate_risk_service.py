
class ClimateRiskService:
    def evaluate(self, event_type, severity):
        return {
            "event_type": event_type,
            "severity": severity,
            "alert": severity in {"high", "critical"}
        }


# ---- additive RUN E (GPT-6): eventos climaticos con alerta ----
# Usa ClimateRiskService.evaluate() real: alert
# True cuando severity high/critical (umbral real).
def evaluate_climate_db(
    db, *, producer_id, event_type,
    severity, detail="",
):
    import time as _t
    import uuid as _u
    base = ClimateRiskService().evaluate(
        event_type, severity
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_climate_events ("
        " event_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " event_type TEXT NOT NULL,"
        " severity TEXT NOT NULL,"
        " alert INTEGER NOT NULL,"
        " detail TEXT NOT NULL DEFAULT '',"
        " created_at TEXT)"
    )
    event_id = (
        "CLM-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_climate_events ("
        " event_id, producer_id,"
        " event_type, severity, alert,"
        " detail, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, producer_id,
         event_type, severity,
         1 if base["alert"] else 0,
         str(detail or ""), ts),
    )
    out = dict(base)
    out["event_id"] = event_id
    out["producer_id"] = producer_id
    return out


def climate_events_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT event_id,"
                    " producer_id, event_type,"
                    " severity, alert, detail,"
                    " created_at FROM"
                    " agro_climate_events WHERE"
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
                    d["alert"] = bool(
                        d.get("alert")
                    )
                    out.append(d)
                return out
    return []
