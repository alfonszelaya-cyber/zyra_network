
class ProductionValidator:
    def validate(self, quantity):
        if quantity <= 0:
            raise ValueError("Production quantity must be positive")
        return True

