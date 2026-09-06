
class ImpactService:
    def calculate(self, affected_units, total_units):
        if total_units <= 0:
            raise ValueError("Total units must be positive")

        return affected_units / total_units

