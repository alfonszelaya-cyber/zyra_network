
class MarketAlertService:
    def evaluate(self, previous_price, current_price, threshold=0.05):
        if previous_price <= 0:
            raise ValueError("Previous price must be positive")

        change = (current_price - previous_price) / previous_price

        if abs(change) >= threshold:
            return {
                "alert": True,
                "change": change,
                "direction": "up" if change > 0 else "down"
            }

        return {
            "alert": False,
            "change": change,
            "direction": "stable"
        }

