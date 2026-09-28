
class ImpactService:
    def calculate(self, affected_units, total_units):
        if total_units <= 0:
            raise ValueError("Total units must be positive")

        return affected_units / total_units


# ---- additive RUN E (GPT-6): impacto persistente ----
# Usa ImpactService.calculate() real (valida
# total_units > 0).
def calculate_impact_db(
    db, *, producer_id, affected_units,
    total_units,
):
    import time as _t
    import uuid as _u
    impact = ImpactService().calculate(
        float(affected_units or 0),
        float(total_units or 0),
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
        " VALUES (?, ?, 'impact',"
        " ?, NULL, ?)",
        (eval_id, producer_id,
         float(impact), ts),
    )
    return {
        "eval_id": eval_id,
        "producer_id": producer_id,
        "impact": round(float(impact), 4),
    }
