
class ProductionTracking:
    def update(self, production_id, status, progress):
        return {
            "production_id": production_id,
            "status": status,
            "progress": progress
        }


# ---- additive PLUS (GPT-2): trazabilidad y timeline ----
def stages_of_db(db, plan_id):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT log_id, plan_id,"
                    " stage, detail, logged_at"
                    " FROM agro_stage_log WHERE"
                    " plan_id = ? ORDER BY"
                    " log_id",
                    (plan_id,),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []


def timeline_of_db(db, producer_id):
    plans = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT plan_id, crop FROM"
                    " agro_plans WHERE"
                    " producer_id = ?",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                plans = list(got)
                break
    out = []
    for p in plans:
        try:
            pid = str(p["plan_id"])
            crop = str(p["crop"])
        except Exception:
            continue
        items = []
        for s in stages_of_db(db, pid):
            items.append({
                "kind": "stage",
                "stage": str(s.get("stage")),
                "detail": str(
                    s.get("detail") or ""
                ),
                "at": str(s.get("logged_at")),
            })
        for name2 in (
            "query_all", "query", "fetchall"
        ):
            fn2 = getattr(db, name2, None)
            if callable(fn2):
                try:
                    igot = fn2(
                        "SELECT kind, severity,"
                        " detail, created_at,"
                        " status FROM"
                        " agro_incidents_plus"
                        " WHERE producer_id = ?"
                        " ORDER BY created_at",
                        (producer_id,),
                    )
                except Exception:
                    igot = None
                if igot:
                    for x in igot:
                        items.append({
                            "kind": "incident",
                            "stage": str(
                                x["kind"]
                            ),
                            "detail": str(
                                x["detail"] or ""
                            ),
                            "at": str(
                                x["created_at"]
                            ),
                            "status": str(
                                x["status"]
                            ),
                        })
                    break
        items.sort(key=lambda x: x["at"])
        out.append({
            "plan_id": pid,
            "crop": crop,
            "timeline": items,
        })
    return out
