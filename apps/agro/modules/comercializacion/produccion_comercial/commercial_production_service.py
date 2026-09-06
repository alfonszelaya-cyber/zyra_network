
class CommercialProductionService:
    def register(self, producer_id, product, quantity, cost=0):
        return {
            "producer_id": producer_id,
            "product": product,
            "quantity": quantity,
            "cost": cost
        }

