
class AgricultureService:
    def register_crop(self, producer_id, crop, area):
        if area <= 0:
            raise ValueError("Area must be positive")

        return {
            "producer_id": producer_id,
            "crop": crop,
            "area": area
        }

