
class DistributionService:
    def assign(self, origin, destination, items):
        return {
            "origin": origin,
            "destination": destination,
            "items": list(items)
        }

