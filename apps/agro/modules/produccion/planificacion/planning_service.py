
class ProductionPlanning:
    def create_plan(self, producer_id, product, target):
        if target <= 0:
            raise ValueError("Target must be positive")

        return {
            "producer_id": producer_id,
            "product": product,
            "target": target,
            "status": "planned"
        }


# ---- additive PLUS (GPT-2): etapas/costos/cancelacion ----
_PLAN_STAGES = (
    "planned", "planted", "growing", "harvested",
)


def create_plan_db(
    db, *, producer_id, unit_id,
    crop, target,
):
    import time as _t
    import uuid as _u
    base = ProductionPlanning().create_plan(
        producer_id, crop, target
    )
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT unit_id FROM"
                    " agro_units WHERE"
                    " unit_id = ?",
                    (unit_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise ValueError(
            "unidad productiva no encontrada: "
            + str(unit_id)
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_plans ("
        " plan_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " unit_id TEXT NOT NULL,"
        " crop TEXT NOT NULL,"
        " target REAL NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_stage_log ("
        " log_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " plan_id TEXT NOT NULL,"
        " stage TEXT NOT NULL,"
        " detail TEXT, logged_at TEXT)"
    )
    plan_id = "PLN-" + _u.uuid4().hex[:10]
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_plans (plan_id,"
        " producer_id, unit_id, crop, target,"
        " status, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'planned', ?)",
        (plan_id, producer_id, unit_id,
         crop, float(target), ts),
    )
    db.execute(
        "INSERT INTO agro_stage_log (plan_id,"
        " stage, detail, logged_at)"
        " VALUES (?, 'planned',"
        " 'plan creado', ?)",
        (plan_id, ts),
    )
    out = dict(base)
    out["plan_id"] = plan_id
    out["unit_id"] = unit_id
    return out


def _plan_status(db, plan_id):
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status FROM"
                    " agro_plans WHERE"
                    " plan_id = ?",
                    (plan_id,),
                )
            except Exception:
                row = None
            if row:
                break
    if not row:
        raise LookupError(
            "plan no encontrado: "
            + str(plan_id)
        )
    try:
        return str(row["status"])
    except Exception:
        return str(row[0])


def advance_plan_plus_db(
    db, *, plan_id, detail="",
):
    import time as _t
    current = _plan_status(db, plan_id)
    if current == "cancelled":
        raise ValueError(
            "plan cancelado: no avanza"
        )
    if current not in _PLAN_STAGES:
        raise ValueError(
            "estado invalido: " + current
        )
    idx = _PLAN_STAGES.index(current)
    if idx >= len(_PLAN_STAGES) - 1:
        raise ValueError(
            "el plan ya esta en la etapa final"
        )
    nxt = _PLAN_STAGES[idx + 1]
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_plans SET status = ?"
        " WHERE plan_id = ?",
        (nxt, plan_id),
    )
    db.execute(
        "INSERT INTO agro_stage_log (plan_id,"
        " stage, detail, logged_at)"
        " VALUES (?, ?, ?, ?)",
        (plan_id, nxt, str(detail or ""), ts),
    )
    return {
        "plan_id": plan_id,
        "from_stage": current,
        "to_stage": nxt,
    }


def cancel_plan_db(
    db, *, plan_id, reason, actor="anon",
):
    import time as _t
    if not str(reason or "").strip():
        raise ValueError(
            "cancelacion requiere motivo"
        )
    current = _plan_status(db, plan_id)
    if current == "harvested":
        raise ValueError(
            "no se puede cancelar un plan"
            " ya cosechado"
        )
    if current == "cancelled":
        raise ValueError(
            "el plan ya esta cancelado"
        )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "UPDATE agro_plans SET"
        " status = 'cancelled'"
        " WHERE plan_id = ?",
        (plan_id,),
    )
    db.execute(
        "INSERT INTO agro_stage_log (plan_id,"
        " stage, detail, logged_at)"
        " VALUES (?, 'cancelled', ?, ?)",
        (plan_id,
         str(reason) + " por " + str(actor),
         ts),
    )
    return {
        "plan_id": plan_id,
        "status": "cancelled",
        "reason": str(reason),
    }


def add_plan_cost_db(
    db, *, plan_id, concept,
    amount, currency, actor="anon",
):
    import time as _t
    amt = float(amount or 0)
    if amt < 0:
        raise ValueError(
            "costo no puede ser negativo"
        )
    if not str(currency or "").strip():
        raise ValueError(
            "moneda obligatoria"
        )
    _plan_status(db, plan_id)
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_plan_costs ("
        " cost_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " plan_id TEXT NOT NULL,"
        " concept TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)"
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_plan_costs (plan_id,"
        " concept, amount, currency, actor,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (plan_id, str(concept), amt,
         str(currency).upper(), str(actor), ts),
    )
    return {
        "plan_id": plan_id,
        "concept": str(concept),
        "amount": amt,
        "currency": str(currency).upper(),
    }


def plan_costs_summary_db(db, plan_id):
    rows = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT concept, amount,"
                    " currency, created_at FROM"
                    " agro_plan_costs WHERE"
                    " plan_id = ? ORDER BY"
                    " cost_id",
                    (plan_id,),
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break
    by_currency = {}
    for r in rows:
        try:
            cur = str(r["currency"])
            amt = float(r["amount"])
        except Exception:
            continue
        by_currency[cur] = (
            by_currency.get(cur, 0.0) + amt
        )
    return {
        "plan_id": plan_id,
        "costs": [dict(r) for r in rows],
        "total_by_currency": by_currency,
        "note": (
            "conversion en vivo: motor"
            " transversal de la Red"
        ),
    }


def plans_plus_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT plan_id, producer_id,"
                    " unit_id, crop, target,"
                    " status, created_at FROM"
                    " agro_plans WHERE"
                    " producer_id = ?"
                    " ORDER BY created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
