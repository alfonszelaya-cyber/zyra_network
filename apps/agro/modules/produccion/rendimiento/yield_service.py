
class YieldService:
    def calculate(self, quantity, area):
        if area <= 0:
            raise ValueError("Area must be positive")

        return quantity / area

