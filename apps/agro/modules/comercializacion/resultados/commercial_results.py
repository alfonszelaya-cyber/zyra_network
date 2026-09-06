
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

