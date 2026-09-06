
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

