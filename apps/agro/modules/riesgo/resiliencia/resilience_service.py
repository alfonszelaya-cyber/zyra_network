
class ResilienceService:
    def recovery_score(self, recovered, affected):
        if affected <= 0:
            raise ValueError("Affected must be positive")

        return recovered / affected


# ---- additive RUN E (GPT-6): score de recuperacion ----
# Usa ResilienceService.recovery_score() real
# (valida affected > 0).
def recovery_score_db(
    db, *, producer_id, risk_id,
    recovered, affected,
):
    import time as _t
    import uuid as _u
    score = ResilienceService().recovery_score(
        float(recovered or 0),
        float(affected or 0),
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
        " VALUES (?, ?, 'recovery',"
        " ?, NULL, ?)",
        (eval_id, producer_id,
         float(score), ts),
    )
    return {
        "eval_id": eval_id,
        "producer_id": producer_id,
        "risk_id": str(risk_id),
        "recovery_score": round(
            float(score), 4
        ),
    }
