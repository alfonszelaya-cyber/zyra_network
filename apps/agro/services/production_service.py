
from apps.agro.domain.entities.production import Production

class ProductionService:
    def create(self, producer_id, product, quantity, unit):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        return Production(
            producer_id=producer_id,
            product=product,
            quantity=quantity,
            unit=unit
        )

    def complete(self, production):
        production.status = "completed"
        production.touch()
        return production

