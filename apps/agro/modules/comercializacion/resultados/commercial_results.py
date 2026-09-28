
class CommercialResults:
    def summarize(self, sales):
        total = sum(
            float(sale.get("total", 0))
            for sale in sales
        )

        return {
            "sales_count": len(sales),
            "total": total
        }


# ---- additive PLUS (GPT-3): resultados por productor ----
def results_for_db(db, producer_id):
    rows = []
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT total FROM"
                    " agro_sales_plus WHERE"
                    " producer_id = ? AND"
                    " status IN ('paid',"
                    " 'delivered', 'closed')"
                    " AND total IS NOT NULL",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break
    sales = []
    for r in rows:
        try:
            sales.append(
                {"total": float(r["total"])}
            )
        except Exception:
            try:
                sales.append(
                    {"total": float(r[0])}
                )
            except Exception:
                pass
    return CommercialResults().summarize(sales)
