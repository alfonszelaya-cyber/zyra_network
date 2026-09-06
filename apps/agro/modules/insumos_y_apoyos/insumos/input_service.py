
class InputService:
    def register(self, product, quantity, unit):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        return {
            "product": product,
            "quantity": quantity,
            "unit": unit
        }

