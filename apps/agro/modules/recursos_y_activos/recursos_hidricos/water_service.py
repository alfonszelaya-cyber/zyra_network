
class WaterResourceService:
    def register(self, location, source_type, capacity=None):
        return {
            "location": location,
            "source_type": source_type,
            "capacity": capacity
        }

