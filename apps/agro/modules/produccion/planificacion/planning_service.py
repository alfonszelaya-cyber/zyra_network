
class ProductionPlanning:
    def create_plan(self, producer_id, product, target):
        if target <= 0:
            raise ValueError("Target must be positive")

        return {
            "producer_id": producer_id,
            "product": product,
            "target": target,
            "status": "planned"
        }

