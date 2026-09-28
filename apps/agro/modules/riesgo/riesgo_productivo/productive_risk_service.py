
class ProductiveRiskService:
    def evaluate(self, losses, production):
        if production <= 0:
            raise ValueError("Production must be positive")

        ratio = losses / production

        return {
            "loss_ratio": ratio,
            "level": (
                "high" if ratio >= 0.5
                else "medium" if ratio >= 0.2
                else "low"
            )
        }


# ---- additive RUN E (GPT-6): evaluacion productiva persistente ----
# Usa ProductiveRiskService.evaluate() real:
# umbrales loss_ratio >=0.5 high, >=0.2 medium.
def evaluate_productive_db(
    db, *, producer_id, losses,
    production, detail="",
):
    import time as _t
    import uuid as _u
    base = ProductiveRiskService().evaluate(
        float(losses or 0), float(production or 0)
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_risk_evals ("
        " eval_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " ratio REAL,"
        " level TEXT,"
        " created_at TEXT)"
    )
    eval_id = (
        "EVL-" + _u.uuid4().hex[:10]
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_risk_evals ("
        " eval_id, producer_id, kind,"
        " ratio, level, created_at)"
        " VALUES (?, ?, 'productive',"
        " ?, ?, ?)",
        (eval_id, producer_id,
         float(base["loss_ratio"]),
         base["level"], ts),
    )
    out = dict(base)
    out["eval_id"] = eval_id
    out["producer_id"] = producer_id
    return out


def evals_of_db(db, producer_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT eval_id,"
                    " producer_id, kind, ratio,"
                    " level, created_at FROM"
                    " agro_risk_evals WHERE"
                    " producer_id = ? ORDER BY"
                    " created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
