
class MarketService:
    def compare_prices(self, prices):
        valid = [float(value) for value in prices if value is not None]

        if not valid:
            return None

        return {
            "minimum": min(valid),
            "maximum": max(valid),
            "average": sum(valid) / len(valid)
        }

