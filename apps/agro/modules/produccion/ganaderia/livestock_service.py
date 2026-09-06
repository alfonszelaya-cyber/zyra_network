
class LivestockService:
    def register_animals(self, producer_id, species, quantity):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        return {
            "producer_id": producer_id,
            "species": species,
            "quantity": quantity
        }

