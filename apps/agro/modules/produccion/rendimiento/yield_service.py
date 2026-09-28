
class YieldService:
    def calculate(self, quantity, area):
        if area <= 0:
            raise ValueError("Area must be positive")

        return quantity / area


# ---- additive PLUS (GPT-2): plan vs producido ----
def report_plus_db(db, store, producer_id):
    planned_rows = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT crop, target FROM"
                    " agro_plans WHERE"
                    " producer_id = ? AND"
                    " status = 'harvested'",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                planned_rows = list(got)
                break
    svc = YieldService()
    planned_total = 0.0
    by_crop = {}
    for p in planned_rows:
        try:
            q = float(p["target"])
            crop = str(p["crop"])
        except Exception:
            continue
        planned_total += q
        by_crop[crop] = (
            by_crop.get(crop, 0.0) + q
        )
    produced_total = 0.0
    by_product = {}
    for prod in store.list_productions():
        if str(
            prod.get("producer_id")
        ) != str(producer_id):
            continue
        try:
            q = float(prod.get("quantity") or 0)
            product = str(prod.get("product"))
        except Exception:
            continue
        produced_total += q
        by_product[product] = (
            by_product.get(product, 0.0) + q
        )
    efficiency = None
    if planned_total > 0:
        efficiency = round(
            svc.calculate(
                produced_total, planned_total
            ),
            4,
        )
    projection = None
    if planned_total > 0:
        projection = round(
            max(
                0.0,
                planned_total - produced_total,
            ),
            4,
        )
    return {
        "producer_id": producer_id,
        "planned_harvested": round(
            planned_total, 4
        ),
        "produced": round(produced_total, 4),
        "efficiency": efficiency,
        "by_crop_planned": by_crop,
        "by_product_produced": by_product,
        "expected_remaining": projection,
    }
