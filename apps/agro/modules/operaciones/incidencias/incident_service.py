
class IncidentService:
    def report(self, operation_id, description, severity="normal"):
        return {
            "operation_id": operation_id,
            "description": description,
            "severity": severity,
            "status": "open"
        }


# ---- additive PLUS (GPT-2): severidad, escalamiento, stats ----
VALID_SEVERITIES = (
    "baja", "media", "alta", "critica",
)


def report_incident_plus_db(
    db, *, producer_id, unit_id=None,
    kind, severity="media", detail="",
):
    import time as _t
    import uuid as _u
    if str(severity) not in VALID_SEVERITIES:
        raise ValueError(
            "severidad invalida"
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_incidents_plus ("
        " incident_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " unit_id TEXT, kind TEXT NOT NULL,"
        " severity TEXT NOT NULL,"
        " detail TEXT, status TEXT NOT NULL,"
        " escalated INTEGER NOT NULL"
        " DEFAULT 0,"
        " action TEXT, resolved_at TEXT,"
        " created_at TEXT)"
    )
    inc_id = "INCAG-" + _u.uuid4().hex[:10]
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    escalated = 1 if severity == "critica" else 0
    db.execute(
        "INSERT INTO agro_incidents_plus ("
        " incident_id, producer_id, unit_id,"
        " kind, severity, detail, status,"
        " escalated, action, resolved_at,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?,"
        " 'open', ?, NULL, NULL, ?)",
        (inc_id, producer_id, unit_id,
         kind, severity, str(detail or ""),
         escalated, ts),
    )
    return {
        "incident_id": inc_id,
        "producer_id": producer_id,
        "kind": kind,
        "severity": severity,
        "status": "open",
        "escalated": bool(escalated),
    }


def open_incidents_plus_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT incident_id,"
                    " producer_id, unit_id,"
                    " kind, severity, detail,"
                    " status, escalated, action,"
                    " created_at FROM"
                    " agro_incidents_plus WHERE"
                    " producer_id = ? AND"
                    " status = 'open'"
                    " ORDER BY created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                out = []
                for r in got:
                    d = dict(r)
                    d["escalated"] = bool(
                        d.get("escalated")
                    )
                    out.append(d)
                return out
    return []


def resolve_incident_plus_db(
    db, *, incident_id, action="",
):
    import time as _t
    if not str(action or "").strip():
        raise ValueError(
            "accion correctiva obligatoria"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_incidents_plus SET"
        " status = 'resolved', action = ?,"
        " resolved_at = ? WHERE"
        " incident_id = ?",
        (str(action), ts, incident_id),
    )
    return {
        "incident_id": incident_id,
        "status": "resolved",
        "action": str(action),
        "resolved_at": ts,
    }


def incident_stats_db(db, producer_id):
    rows = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT severity, status FROM"
                    " agro_incidents_plus WHERE"
                    " producer_id = ?",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break
    by_severity = {}
    by_status = {}
    for r in rows:
        try:
            sev = str(r["severity"])
            stt = str(r["status"])
        except Exception:
            continue
        by_severity[sev] = (
            by_severity.get(sev, 0) + 1
        )
        by_status[stt] = (
            by_status.get(stt, 0) + 1
        )
    return {
        "producer_id": producer_id,
        "total": len(rows),
        "by_severity": by_severity,
        "by_status": by_status,
    }
