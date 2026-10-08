
from datetime import datetime, timezone

class AgroAuditService:
    def record(self, actor_id, action, resource, resource_id):
        return {
            "actor_id": actor_id,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ---- additive PLUS (GPT-7): auditoria en cadena ----
# FIX v4: la columna detail guarda el detalle CRUDO
# (no el JSON envuelto) para que el hash de
# verify recalcule identico.
def _agro_audit_chain_record(
    db, *, actor_id, role,
    operation, outcome, detail="",
):
    import hashlib as _hl
    import time as _t
    base = AgroAuditService().record(
        actor_id, operation, "agro", operation
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_audit_chain ("
        " seq INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " ts TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " role TEXT NOT NULL,"
        " operation TEXT NOT NULL,"
        " outcome TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT '',"
        " prev_hash TEXT NOT NULL,"
        " event_hash TEXT NOT NULL)"
    )
    prev = ""
    for name in ("query_one", "query"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT event_hash FROM"
                    " agro_audit_chain ORDER"
                    " BY seq DESC LIMIT 1"
                )
            except Exception:
                row = None
            if row:
                try:
                    prev = str(row["event_hash"])
                except Exception:
                    try:
                        prev = str(row[0])
                    except Exception:
                        prev = ""
                break
    ts = str(base["timestamp"])
    raw_detail = str(detail or "")
    event_hash = _hl.sha256(
        (prev + "|" + ts + "|" + str(actor_id)
         + "|" + str(role) + "|" + str(operation)
         + "|" + str(outcome) + "|"
         + raw_detail).encode("utf-8")
    ).hexdigest()
    db.execute(
        "INSERT INTO agro_audit_chain ("
        " ts, actor, role, operation,"
        " outcome, detail, prev_hash,"
        " event_hash)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, str(actor_id), str(role),
         str(operation), str(outcome),
         raw_detail, prev, event_hash),
    )
    return event_hash


def _agro_audit_chain_verify(db):
    import hashlib as _hl
    rows = []
    for name in (
        "query_all", "query", "fetchall"
    ):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT seq, ts, actor,"
                    " role, operation, outcome,"
                    " detail, prev_hash,"
                    " event_hash FROM"
                    " agro_audit_chain"
                    " ORDER BY seq ASC"
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break

    def g(row, key, idx):
        try:
            return str(row[key])
        except Exception:
            try:
                return str(row[idx])
            except Exception:
                return ""

    prev = ""
    count = 0
    broken_at = None
    for row in rows:
        try:
            seq = int(row["seq"])
        except Exception:
            try:
                seq = int(row[0])
            except Exception:
                continue
        ts = g(row, "ts", 1)
        actor = g(row, "actor", 2)
        role = g(row, "role", 3)
        op = g(row, "operation", 4)
        oc = g(row, "outcome", 5)
        dt = g(row, "detail", 6)
        ph = g(row, "prev_hash", 7)
        eh = g(row, "event_hash", 8)
        calc = _hl.sha256(
            (ph + "|" + ts + "|" + actor
             + "|" + role + "|" + op
             + "|" + oc + "|"
             + dt).encode("utf-8")
        ).hexdigest()
        if ph != prev or eh != calc:
            broken_at = seq
            break
        prev = eh
        count += 1
    return {
        "ok": broken_at is None,
        "entries": len(rows),
        "verified": count,
        "broken_at": broken_at,
    }


def _agro_audit_chain_list(
    db, limit=50, offset=0,
):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT seq, ts, actor, role,"
                    " operation, outcome, detail"
                    " FROM agro_audit_chain"
                    " ORDER BY seq DESC LIMIT ?"
                    " OFFSET ?",
                    (int(limit), int(offset)),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
