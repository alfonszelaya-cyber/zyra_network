
class AgriculturalTechnology:
    def ingest(self, device_id, data):
        return {
            "device_id": device_id,
            "data": dict(data)
        }

