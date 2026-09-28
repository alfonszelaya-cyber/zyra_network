
class RiskAlertService:
    def create(self, risk_type, severity, target):
        return {
            "risk_type": risk_type,
            "severity": severity,
            "target": target
        }


# ---- additive RUN E (GPT-6): alertas persistentes ----
# Usa RiskAlertService.create() real.
def create_alert_db(
    db, *, producer_id, risk_type,
    severity, target, detail="",
):
    import time as _t
    import uuid as _u
    base = RiskAlertService().create(
        risk_type, severity, target
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_alerts ("
        " alert_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " risk_type TEXT NOT NULL,"
        " severity TEXT NOT NULL,"
        " target TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT '',"
        " status TEXT NOT NULL,"
        " resolution TEXT,"
        " created_at TEXT,"
        " resolved_at TEXT)"
    )
    alert_id = (
        "ALR-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_alerts ("
        " alert_id, producer_id,"
        " risk_type, severity, target,"
        " detail, status, resolution,"
        " created_at, resolved_at)"
        " VALUES (?, ?, ?, ?, ?, ?,"
        " 'open', NULL, ?, NULL)",
        (alert_id, producer_id,
         risk_type, severity, target,
         str(detail or ""), ts),
    )
    out = dict(base)
    out["alert_id"] = alert_id
    out["producer_id"] = producer_id
    out["status"] = "open"
    return out


def open_alerts_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT alert_id,"
                    " producer_id, risk_type,"
                    " severity, target, detail,"
                    " status, created_at FROM"
                    " agro_alerts WHERE"
                    " producer_id = ? AND"
                    " status = 'open' ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def resolve_alert_db(
    db, *, alert_id, resolution,
):
    import time as _t
    if not str(resolution or "").strip():
        raise ValueError(
            "resolucion obligatoria"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_alerts SET"
        " status = 'resolved',"
        " resolution = ?, resolved_at = ?"
        " WHERE alert_id = ?",
        (str(resolution), ts, alert_id),
    )
    return {
        "alert_id": alert_id,
        "status": "resolved",
        "resolution": str(resolution),
    }
