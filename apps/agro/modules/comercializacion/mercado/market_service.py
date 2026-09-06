
class MarketService:
    def snapshot(self, product, prices):
        values = [float(p) for p in prices]

        if not values:
            raise ValueError("Prices are required")

        return {
            "product": product,
            "minimum": min(values),
            "maximum": max(values),
            "average": sum(values) / len(values)
        }

