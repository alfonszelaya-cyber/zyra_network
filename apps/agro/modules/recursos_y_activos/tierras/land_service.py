
class LandService:
    def register(self, producer_id, area, location, tenure=None):
        if area <= 0:
            raise ValueError("Area must be positive")

        return {
            "producer_id": producer_id,
            "area": area,
            "location": location,
            "tenure": tenure
        }

